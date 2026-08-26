"""Asyncio orchestrator — Phase E: voice pipeline + WebSocket event API."""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

_AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

from api.event_bus import EventBus
from api.ws_server import run_ws_server
from asr.asr_engine import AsrEngine, AsrEngineConfig
from asr.normalize import normalize_user_text
from asr.sense_voice import SenseVoiceConfig
from asr.sherpa_streaming_asr import StreamingParaformerConfig
from asr.vad_stream import VadConfig, VadStream
from llm.client import llm_chat_stream, llm_clear_history, llm_ping
from orchestrator.config_loader import load_yaml
from orchestrator.events import AgentState
from tts.sentence_split import (
    canned_reply_for,
    cap_speak_text,
    count_cjk,
    drain_complete_sentences,
    extract_speak_sentences,
    is_robotic_reply,
    persona_reply_for,
)
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
        self._turn_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._asr_session = None
        self._listen_cooldown_until = 0.0
        self._turn_busy = False
        self._speaking = False
        self._tts_abort = False

        vad_cfg = cfg.get("vad") or {}
        asr_cfg = cfg.get("asr") or {}
        tts_cfg = cfg.get("tts") or {}
        api_cfg = cfg.get("api") or {}
        paths = cfg.get("paths") or {}
        barge_cfg = cfg.get("barge_in") or {}

        self.event_bus = EventBus()
        self.api_enabled = str(api_cfg.get("enabled", "true")).lower() not in ("0", "false", "no")
        self.api_host = str(api_cfg.get("host", "127.0.0.1"))
        self.api_port = int(api_cfg.get("port", 8765))
        self.barge_in_enabled = str(barge_cfg.get("enabled", "true")).lower() not in ("0", "false", "no")
        self.barge_in_min_sec = float(barge_cfg.get("min_speech_sec", 0.35))

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
        self.listen_cooldown_sec = float(vad_cfg.get("listen_cooldown_sec", 0.8))

        utterance = paths.get("utterance_wav", str(agent_root / "run" / "last_utterance.wav"))
        asr_backend = str(asr_cfg.get("backend", "sense_voice")).strip().lower()
        self.asr_engine = AsrEngine(
            AsrEngineConfig(
                backend=asr_backend,
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
                streaming_paraformer=StreamingParaformerConfig(
                    model_dir=asr_cfg.get(
                        "model_dir",
                        "/userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en",
                    ),
                    sherpa_lib=asr_cfg.get(
                        "sherpa_lib",
                        "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
                    ),
                    encoder=str(asr_cfg.get("encoder", "encoder.int8.onnx")),
                    decoder=str(asr_cfg.get("decoder", "decoder.int8.onnx")),
                    tokens=str(asr_cfg.get("tokens", "tokens.txt")),
                    num_threads=int(asr_cfg.get("num_threads", 2)),
                    sample_rate=int(vad_cfg.get("sample_rate", 16000)),
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
        self.max_speak_chars = int(tts_cfg.get("max_speak_chars", 100))
        self.system_prompt = (cfg.get("system_prompt") or "").strip()
        self.vad_stream = VadStream(self.vad_config, self.vad_queue)
        self.tts_queue = TtsQueue(
            TtsEngine(
                TtsConfig(
                    backend=str(tts_cfg.get("backend", "matcha")),
                    model_dir=tts_cfg.get("model_dir", "/userdata/voice/matcha-icefall-zh-baker"),
                    vocoder=tts_cfg.get("vocoder", "/userdata/voice/vocos-22khz-univ.onnx"),
                    rule_fsts=list(tts_cfg.get("rule_fsts") or []),
                    sherpa_bin=tts_cfg.get(
                        "sherpa_bin",
                        "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline-tts",
                    ),
                    sherpa_lib=tts_cfg.get(
                        "sherpa_lib",
                        "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
                    ),
                    num_threads=int(tts_cfg.get("num_threads", 2)),
                    sid=int(tts_cfg.get("sid", 0)),
                    speed=float(tts_cfg.get("speed", 1.0)),
                    max_chars=int(tts_cfg.get("max_chars", 80)),
                )
            ),
            merge_max_chars=int(tts_cfg.get("merge_max_chars", 40)),
        )
        self._loop: asyncio.AbstractEventLoop | None = None

    async def emit(self, event: dict[str, Any]) -> None:
        await self.event_bus.publish(event)

    def set_state(self, new: AgentState) -> None:
        if new != self.state:
            LOG.info("[state] %s -> %s", self.state.value, new.value)
            self.state = new
            asyncio.create_task(self.emit({"type": "state", "value": new.value}))

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
            await self.emit({"type": "asr_partial", "text": text})

        async def on_final(text: str, meta: dict) -> None:
            LOG.info("[event] asr_final: %s", text or meta.get("status"))
            await self.emit({"type": "asr_final", "text": text, "meta": meta})

        self._asr_session = self.asr_engine.create_session(on_partial, on_final)
        return self._asr_session

    async def _interrupt_tts(self) -> None:
        if not self._speaking:
            return
        LOG.info("[barge-in] interrupt TTS playback")
        self._tts_abort = True
        self._listen_cooldown_until = 0.0
        await self.tts_queue.interrupt()
        await self.emit({"type": "barge_in", "phase": "tts"})

    async def run_vad_loop(self, inject_wav: str | None = None) -> None:
        try:
            if inject_wav:
                await self.vad_stream.run_wav_file(inject_wav)
            else:
                await self.vad_stream.run_live()
        finally:
            await self.vad_queue.put({"type": "shutdown"})

    async def _turn_worker(self) -> None:
        while True:
            event = await self._turn_queue.get()
            try:
                await self._process_turn(event)
            finally:
                self._turn_queue.task_done()

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
                if self.barge_in_enabled and self._speaking:
                    await self._interrupt_tts()
                self._new_asr_session()
                await self._asr_session.start()
                continue
            if etype == "speech_end":
                LOG.info("[event] speech_end")
                continue
            if etype == "audio_chunk" and self._asr_session and (not self._turn_busy or self._speaking):
                await self._asr_session.feed(event["samples"])
                continue
            if etype == "audio_segment":
                duration = float(event.get("duration_sec", 0.0))
                if self._turn_busy and not self._speaking:
                    LOG.info("[vad] busy ASR/LLM, drop %.2fs segment", duration)
                    continue
                if not self._speaking and time.monotonic() < self._listen_cooldown_until:
                    LOG.info("[vad] post-tts cooldown, skip %.2fs segment", duration)
                    continue
                if self.barge_in_enabled and self._speaking:
                    if duration < self.barge_in_min_sec:
                        LOG.info("[barge-in] segment too short (%.2fs), skip", duration)
                        continue
                    await self._interrupt_tts()
                await self._turn_queue.put(event)

    async def _process_turn(self, event: dict[str, Any]) -> None:
        self._turn_busy = True
        self._tts_abort = False
        self.tts_queue.mark_utterance_start()
        duration = event.get("duration_sec", 0.0)
        LOG.info("[event] audio_segment %.2fs", duration)
        self.set_state(AgentState.ASR)
        session = self._asr_session
        try:
            if not session:
                session = self._new_asr_session()
                await session.start()
            result = await session.finalize_samples(event["samples"])
            text = normalize_user_text((result.get("text") or "").strip())
            if text:
                LOG.info("[asr] normalized: %s", text)
                await self._run_llm(text)
            else:
                LOG.info("[asr] no text recognized")
        finally:
            if self._asr_session is session:
                self._asr_session = None
            self._speaking = False
            self._turn_busy = False
            self.set_state(AgentState.LISTEN)

    async def _enqueue_speak(self, text: str, tts_state: dict[str, int | bool]) -> bool:
        if self._tts_abort:
            return False
        remaining = self.max_speak_chars - int(tts_state["cjk"])
        speak = cap_speak_text(text, remaining)
        if not speak:
            return False
        tts_state["n"] = int(tts_state["n"]) + 1
        tts_state["cjk"] = int(tts_state["cjk"]) + count_cjk(speak)
        LOG.info("[event] tts_sentence: %s", speak[:60])
        await self.emit({"type": "tts_sentence", "text": speak})
        await self.tts_queue.enqueue(speak)
        return True

    async def _run_llm(self, prompt: str) -> None:
        user_prompt = prompt
        self.set_state(AgentState.LLM)
        await asyncio.to_thread(llm_clear_history, self.socket_path)
        if self.system_prompt:
            prompt = f"{self.system_prompt}\n\n用户：{prompt}\n小揽："
        LOG.info("[llm] prompt %d chars · user=%s", len(prompt), user_prompt[:48])
        buffer = {"text": ""}
        turn_tainted = {"v": False}
        tts_state: dict[str, int | bool] = {"n": 0, "cjk": 0, "canned": False}
        loop = asyncio.get_running_loop()

        def _enqueue_tts(sent: str) -> None:
            if self._tts_abort or turn_tainted["v"] or int(tts_state["cjk"]) >= self.max_speak_chars:
                return
            speak = sent
            if is_robotic_reply(speak):
                canned = canned_reply_for(user_prompt)
                if not canned:
                    turn_tainted["v"] = True
                    return
                speak = canned
                tts_state["canned"] = True
            remaining = self.max_speak_chars - int(tts_state["cjk"])
            speak = cap_speak_text(speak, remaining)
            if not speak:
                return
            tts_state["n"] = int(tts_state["n"]) + 1
            tts_state["cjk"] = int(tts_state["cjk"]) + count_cjk(speak)
            LOG.info("[event] tts_sentence: %s", speak[:60])
            asyncio.run_coroutine_threadsafe(
                self.emit({"type": "tts_sentence", "text": speak}),
                loop,
            )
            asyncio.run_coroutine_threadsafe(self.tts_queue.enqueue(speak), loop)

        def on_token(piece: str) -> None:
            if self._tts_abort:
                return
            buffer["text"] += piece
            if is_robotic_reply(buffer["text"]):
                turn_tainted["v"] = True
            asyncio.run_coroutine_threadsafe(
                self.emit({"type": "llm_token", "text": piece}),
                loop,
            )
            if turn_tainted["v"]:
                return
            complete, buffer["text"] = drain_complete_sentences(buffer["text"])
            for sent in complete:
                _enqueue_tts(sent)
                if int(tts_state["cjk"]) >= self.max_speak_chars:
                    break

        try:
            reply = await asyncio.to_thread(
                llm_chat_stream,
                prompt,
                on_token,
                sock_path=self.socket_path,
                max_new_tokens=self.max_new_tokens,
            )
            full = reply["text"]
            if not self._tts_abort and (turn_tainted["v"] or is_robotic_reply(full)):
                await self.tts_queue.discard_pending()
                tts_state = {"n": 0, "cjk": 0, "canned": True}
                speak = persona_reply_for(user_prompt)
                LOG.info("[llm] persona fallback: %s", speak[:48])
                await self._enqueue_speak(speak, tts_state)
            elif int(tts_state["n"]) == 0 and not self._tts_abort:
                for sent in extract_speak_sentences(full, self.max_speak_chars):
                    if not await self._enqueue_speak(sent, tts_state):
                        break
                    if int(tts_state["cjk"]) >= self.max_speak_chars:
                        break
            LOG.info(
                "[llm] reply (%d chars, ttft=%.3fs): %s",
                len(full),
                reply.get("ttft_s") or 0,
                full[:120],
            )
            if int(tts_state["n"]) > 0 and not self._tts_abort:
                self.set_state(AgentState.TTS)
                self._speaking = True
                try:
                    await self.tts_queue.wait_done()
                finally:
                    self._speaking = False
                if not self._tts_abort:
                    self._listen_cooldown_until = time.monotonic() + self.listen_cooldown_sec
                lat = self.tts_queue.first_play_latency_s
                if lat is not None:
                    LOG.info("[tts] utterance first_play=%.2fs (target <4s)", lat)
            elif self._tts_abort:
                LOG.info("[barge-in] skipped post-abort cooldown")
        except OSError as exc:
            LOG.error("[llm] request failed: %s", exc)

    async def run(self, inject_wav: str | None = None) -> None:
        (self.agent_root / "run").mkdir(parents=True, exist_ok=True)
        (self.agent_root / "logs").mkdir(parents=True, exist_ok=True)
        self.set_state(AgentState.IDLE)
        self.ping_llm_daemon()
        await self.tts_queue.start()
        if self.api_enabled:
            await run_ws_server(self.event_bus, self.api_host, self.api_port)
        await asyncio.gather(
            self.run_vad_loop(inject_wav),
            self.handle_events(),
            self._turn_worker(),
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="R1 agent orchestrator (Phase E)")
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
    LOG.info("=== R1 orchestrator Phase E ===")
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
