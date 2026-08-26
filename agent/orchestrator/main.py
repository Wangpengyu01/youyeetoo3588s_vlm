"""Asyncio orchestrator — Phase D: VAD → ASR → LLM stream → TTS queue."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

_AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

from asr.asr_engine import AsrEngine, AsrEngineConfig
from asr.sense_voice import SenseVoiceConfig
from asr.vad_stream import VadConfig, VadStream
from llm.client import llm_chat_stream, llm_ping
from orchestrator.config_loader import load_yaml
from orchestrator.events import AgentState
from tts.sentence_split import drain_complete_sentences, flush_remainder
from tts.tts_engine import TtsConfig, TtsEngine
from tts.tts_queue import TtsQueue

LOG = logging.getLogger("orchestrator")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


class Orchestrator:
    def __init__(self, cfg: dict[str, Any], agent_root: Path) -> None:
        self.cfg = cfg
        self.agent_root = agent_root
        self.state = AgentState.IDLE
        self.vad_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._busy = False
        self._asr_session = None

        vad_cfg = cfg.get("vad") or {}
        asr_cfg = cfg.get("asr") or {}
        tts_cfg = cfg.get("tts") or {}
        paths = cfg.get("paths") or {}

        self.vad_config = VadConfig(
            model_path=vad_cfg.get("model", "/userdata/voice/silero_vad.onnx"),
            sherpa_lib=vad_cfg.get(
                "sherpa_lib",
                "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
            ),
            sample_rate=int(vad_cfg.get("sample_rate", 16000)),
            chunk_ms=int(vad_cfg.get("chunk_ms", 100)),
            threshold=float(vad_cfg.get("threshold", 0.5)),
            min_silence_duration=float(vad_cfg.get("min_silence_duration", 0.4)),
            min_speech_duration=float(vad_cfg.get("min_speech_duration", 0.25)),
            max_speech_duration=float(vad_cfg.get("max_speech_duration", 30.0)),
            alsa_device=str(vad_cfg.get("alsa_device", "plughw:0,0")),
            min_segment_sec=float(vad_cfg.get("min_segment_sec", 0.5)),
        )

        utterance = paths.get("utterance_wav", str(agent_root / "run" / "last_utterance.wav"))
        self.asr_engine = AsrEngine(
            AsrEngineConfig(
                sense_voice=SenseVoiceConfig(
                    model_dir=asr_cfg.get(
                        "model_dir",
                        "/userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17",
                    ),
                    sherpa_bin=asr_cfg.get(
                        "sherpa_bin",
                        "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline",
                    ),
                    sherpa_lib=asr_cfg.get(
                        "sherpa_lib",
                        "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
                    ),
                    language=str(asr_cfg.get("language", "zh")),
                    num_threads=int(asr_cfg.get("num_threads", 2)),
                ),
                sample_rate=self.vad_config.sample_rate,
                partial_interval_sec=float(asr_cfg.get("partial_interval_sec", 1.2)),
                partial_min_sec=float(asr_cfg.get("partial_min_sec", 1.0)),
                partial_enabled=str(asr_cfg.get("partial_enabled", "true")).lower() not in ("0", "false", "no"),
                max_partials_per_utterance=int(asr_cfg.get("max_partials_per_utterance", 3)),
                min_duration_sec=self.vad_config.min_segment_sec,
                utterance_wav=utterance,
            )
        )

        self.socket_path = cfg.get("socket_path", "/tmp/r1-llm.sock")
        self.max_new_tokens = int(cfg.get("max_new_tokens", 64))
        self.vad_stream = VadStream(self.vad_config, self.vad_queue)
        self.tts_queue = TtsQueue(
            TtsEngine(
                TtsConfig(
                    model_dir=tts_cfg.get("model_dir", "/userdata/voice/vits-melo-tts-zh_en"),
                    sherpa_bin=tts_cfg.get(
                        "sherpa_bin",
                        "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline-tts",
                    ),
                    sherpa_lib=tts_cfg.get(
                        "sherpa_lib",
                        "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
                    ),
                    num_threads=int(tts_cfg.get("num_threads", 2)),
                    max_chars=int(tts_cfg.get("max_chars", 120)),
                )
            )
        )
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_state(self, new: AgentState) -> None:
        if new != self.state:
            LOG.info("[state] %s -> %s", self.state.value, new.value)
            self.state = new

    def ping_llm_daemon(self) -> bool:
        if not Path(self.socket_path).exists():
            LOG.warning("[llm] socket missing: %s", self.socket_path)
            return False
        try:
            ok = llm_ping(self.socket_path)
            LOG.info("[llm] ping %s", "ok" if ok else "fail")
            return ok
        except OSError as exc:
            LOG.warning("[llm] ping failed: %s", exc)
            return False

    def _new_asr_session(self):
        async def on_partial(text: str) -> None:
            LOG.info("[event] asr_partial: %s", text)

        async def on_final(text: str, meta: dict) -> None:
            LOG.info("[event] asr_final: %s", text or meta.get("status"))

        self._asr_session = self.asr_engine.create_session(on_partial, on_final)
        return self._asr_session

    async def run_vad_loop(self, inject_wav: str | None = None) -> None:
        try:
            if inject_wav:
                await self.vad_stream.run_wav_file(inject_wav)
            else:
                await self.vad_stream.run_live()
        finally:
            await self.vad_queue.put({"type": "shutdown"})

    async def handle_events(self) -> None:
        self.set_state(AgentState.LISTEN)
        while True:
            event = await self.vad_queue.get()
            etype = event.get("type")
            if etype == "shutdown":
                LOG.info("[event] shutdown")
                break
            if etype == "error":
                LOG.error("[event] %s", event)
                continue
            if etype == "speech_start":
                LOG.info("[event] speech_start")
                self._new_asr_session()
                await self._asr_session.start()
                continue
            if etype == "speech_end":
                LOG.info("[event] speech_end")
                continue
            if etype == "audio_chunk" and self._asr_session and not self._busy:
                await self._asr_session.feed(event["samples"])
                continue
            if etype == "audio_segment" and not self._busy:
                await self._on_segment(event)

    async def _on_segment(self, event: dict[str, Any]) -> None:
        self._busy = True
        self.tts_queue.mark_utterance_start()
        duration = event.get("duration_sec", 0.0)
        LOG.info("[event] audio_segment %.2fs", duration)
        self.set_state(AgentState.ASR)
        try:
            if not self._asr_session:
                self._new_asr_session()
                await self._asr_session.start()
            result = await self._asr_session.finalize_samples(event["samples"])
            text = (result.get("text") or "").strip()
            if text:
                await self._run_llm(text)
            else:
                LOG.info("[asr] no text recognized")
        finally:
            self._asr_session = None
            self.set_state(AgentState.LISTEN)
            self._busy = False

    async def _run_llm(self, prompt: str) -> None:
        self.set_state(AgentState.LLM)
        buffer = {"text": ""}
        loop = asyncio.get_running_loop()

        def on_token(piece: str) -> None:
            buffer["text"] += piece
            complete, buffer["text"] = drain_complete_sentences(buffer["text"])
            for sent in complete:
                LOG.info("[event] tts_sentence: %s", sent[:60])
                asyncio.run_coroutine_threadsafe(self.tts_queue.enqueue(sent), loop)

        try:
            reply = await asyncio.to_thread(
                llm_chat_stream,
                prompt,
                on_token,
                sock_path=self.socket_path,
                max_new_tokens=self.max_new_tokens,
            )
            for sent in flush_remainder(buffer["text"]):
                LOG.info("[event] tts_sentence: %s", sent[:60])
                await self.tts_queue.enqueue(sent)
            LOG.info(
                "[llm] reply (%d chars, ttft=%.3fs): %s",
                len(reply["text"]),
                reply.get("ttft_s") or 0,
                reply["text"][:120],
            )
            self.set_state(AgentState.TTS)
            await self.tts_queue.wait_done()
            lat = self.tts_queue.first_play_latency_s
            if lat is not None:
                LOG.info("[tts] utterance first_play=%.2fs (target <4s)", lat)
        except OSError as exc:
            LOG.error("[llm] request failed: %s", exc)

    async def run(self, inject_wav: str | None = None) -> None:
        (self.agent_root / "run").mkdir(parents=True, exist_ok=True)
        (self.agent_root / "logs").mkdir(parents=True, exist_ok=True)
        self.set_state(AgentState.IDLE)
        self.ping_llm_daemon()
        await self.tts_queue.start()
        await asyncio.gather(self.run_vad_loop(inject_wav), self.handle_events())


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="R1 agent orchestrator (Phase D)")
    parser.add_argument("--config", default="/userdata/agent/config/agent.yaml")
    parser.add_argument("--agent-root", default="/userdata/agent")
    parser.add_argument("--inject-wav", help="offline test: feed wav instead of mic")
    parser.add_argument("--no-partial", action="store_true", help="disable partial ASR (faster offline test)")
    parser.add_argument("--no-tts", action="store_true", help="skip TTS playback")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    agent_root = Path(args.agent_root)
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))

    cfg = load_yaml(args.config)
    setup_logging(args.log_level)
    LOG.info("=== R1 orchestrator Phase D ===")
    orch = Orchestrator(cfg, agent_root)
    if args.no_partial or args.inject_wav:
        orch.asr_engine.cfg.partial_enabled = False
    if args.no_tts:
        async def _noop_enqueue(text: str) -> None:
            LOG.info("[tts] skipped: %s", text[:60])

        async def _noop_wait() -> None:
            return None

        orch.tts_queue.enqueue = _noop_enqueue  # type: ignore[method-assign]
        orch.tts_queue.wait_done = _noop_wait  # type: ignore[method-assign]
    try:
        asyncio.run(orch.run(inject_wav=args.inject_wav))
    except KeyboardInterrupt:
        LOG.info("stopped")


if __name__ == "__main__":
    main()
