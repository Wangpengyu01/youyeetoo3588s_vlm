"""Asyncio orchestrator — Phase E: voice pipeline + WebSocket event API."""
from __future__ import annotations

import asyncio
import logging
import re
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
    StreamingSentenceSplitter,
    canned_reply_for,
    clean_llm_reply,
    extract_speak_sentences,
    is_off_topic_reply,
    is_robotic_reply,
    is_spurious_name_reply,
    is_speakable,
    persona_reply_for,
    sanitize_tts_text,
    should_skip_llm,
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
            speech_preroll_ms=int(vad_cfg.get("speech_preroll_ms", 400)),
            arecord_period_size=int(vad_cfg.get("arecord_period_size", 320)),
            arecord_buffer_size=int(vad_cfg.get("arecord_buffer_size", 2560)),
            mic_capture_gain=int(vad_cfg.get("mic_capture_gain", 6)),
        )
        self.listen_cooldown_sec = float(vad_cfg.get("listen_cooldown_sec", 0.5))
        self.listen_cooldown_skip_max_sec = float(vad_cfg.get("listen_cooldown_skip_max_sec", 0.45))

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
                clip_peak_threshold=int(asr_cfg.get("clip_peak_threshold", 30000)),
                clip_limit_ceiling=float(asr_cfg.get("clip_limit_ceiling", 0.85)),
            )
        )

        self.socket_path = cfg.get("socket_path", "/tmp/r1-llm.sock")
        self.max_new_tokens = int(cfg.get("max_new_tokens", 64))
        self.history_max_turns = int(cfg.get("history_max_turns", 4))
        self.history_idle_clear_sec = float(cfg.get("history_idle_clear_sec", 600))
        self.system_prompt = (cfg.get("system_prompt") or "").strip()
        self._chat_turns: list[tuple[str, str]] = []
        self._llm_last_turn_at = 0.0
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
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.emit({"type": "state", "value": new.value}))
            except RuntimeError:
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.emit({"type": "state", "value": new.value}), self._loop
                    )

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
            if self.barge_in_enabled and self._speaking and text.strip():
                clean_p = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", text)
                if len(clean_p) >= 1:
                    LOG.info("[barge-in] user spoke (%s), interrupting TTS immediately", text)
                    await self._interrupt_tts()

        async def on_final(text: str, meta: dict) -> None:
            LOG.info("[event] asr_final: %s", text or meta.get("status"))
            await self.emit({"type": "asr_final", "text": text, "meta": meta})

        self._asr_session = self.asr_engine.create_session(on_partial, on_final)
        return self._asr_session

    async def _interrupt_tts(self) -> None:
        if not self._speaking:
            return
        LOG.info("[barge-in] interrupt TTS playback immediately")
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
                if self._speaking:
                    LOG.info("[barge-in] speech segment %.2fs detected during TTS, interrupting playback immediately", duration)
                    await self._interrupt_tts()
                    await self._turn_queue.put(event)
                    continue
                if self._turn_busy and not self._speaking and not self._tts_abort:
                    if duration >= 0.8:
                        LOG.info("[vad] busy turn, but segment is valid user speech (%.2fs), queuing", duration)
                        await self._turn_queue.put(event)
                        continue
                    LOG.info("[vad] busy ASR/LLM, drop %.2fs segment", duration)
                    continue
                if (
                    not self._speaking
                    and time.monotonic() < self._listen_cooldown_until
                    and duration < self.listen_cooldown_skip_max_sec
                ):
                    LOG.info("[vad] post-tts cooldown, skip short %.2fs segment", duration)
                    continue
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
        speak = sanitize_tts_text(text)
        if not is_speakable(speak):
            return False
        tts_state["n"] = int(tts_state["n"]) + 1
        if self.state != AgentState.TTS:
            self.set_state(AgentState.TTS)
        self._speaking = True
        LOG.info("[event] tts_sentence: %s", speak[:60])
        await self.emit({"type": "tts_sentence", "text": speak})
        await self.tts_queue.enqueue(speak)
        return True

    async def _speak_extracted(self, full: str, *, canned: bool = False) -> None:
        """Enqueue every complete sentence in full — no char/sentence cap."""
        tts_state: dict[str, int | bool] = {"n": 0, "canned": canned}
        sents = extract_speak_sentences(full, max_cjk=99999)
        if not sents:
            return
        LOG.info("[tts] speak plan: %d sentence(s)", len(sents))
        for sent in sents:
            if not await self._enqueue_speak(sent, tts_state):
                break
        if int(tts_state["n"]) <= 0 or self._tts_abort:
            return
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

    async def _prepare_llm_call(self) -> None:
        now = time.monotonic()
        if self._chat_turns and self.history_idle_clear_sec > 0:
            idle = now - self._llm_last_turn_at
            if idle >= self.history_idle_clear_sec:
                LOG.info(
                    "[llm] idle %.0fs >= %.0fs, clearing transcript",
                    idle,
                    self.history_idle_clear_sec,
                )
                self._chat_turns.clear()
        await asyncio.to_thread(llm_clear_history, self.socket_path)

    def _build_llm_prompt(self, user_text: str) -> str:
        prompt = ""
        if self.system_prompt:
            prompt += f"<|im_start|>system\n{self.system_prompt.strip()}<|im_end|>\n"
        for user, assistant in self._chat_turns[-self.history_max_turns :]:
            prompt += f"<|im_start|>user\n{user.strip()}<|im_end|>\n<|im_start|>assistant\n{assistant.strip()}<|im_end|>\n"
        prompt += f"<|im_start|>user\n{user_text.strip()}<|im_end|>\n<|im_start|>assistant\n"
        return prompt

    def _record_chat_turn(self, user: str, assistant: str) -> None:
        text = assistant.strip()
        if not text:
            return
        if self._chat_turns and self._chat_turns[-1][1].strip() == text:
            LOG.warning("[llm] repetition detected in record_turn, wiping history")
            self._chat_turns.clear()
            return
        self._chat_turns.append((user, text))
        if len(self._chat_turns) > self.history_max_turns:
            self._chat_turns = self._chat_turns[-self.history_max_turns :]
        self._llm_last_turn_at = time.monotonic()
        LOG.info("[llm] transcript stored (%d/%d turns)", len(self._chat_turns), self.history_max_turns)

    async def _speak_turn(self, text: str) -> None:
        await self._speak_extracted(text, canned=True)

    async def _run_llm(self, prompt: str) -> None:
        user_prompt = prompt
        self.set_state(AgentState.LLM)

        u_clean = user_prompt.strip()
        STOP_PAT = re.compile(r"(停|暂停|别说了|闭嘴|算了|打住|停止|停下|别讲|不要说|闭上嘴|别出声|安静|停一下)")
        if STOP_PAT.search(u_clean):
            self._chat_turns.clear()
            await asyncio.to_thread(llm_clear_history, self.socket_path)
            LOG.info("[llm] user requested session reset / stop: %s", u_clean)
            await self._speak_turn("好的。")
            return

        if len(u_clean) <= 1 or re.search(r"^[啊嗯呃哦用呀吧呵哈嘿]+$", u_clean):
            LOG.info("[llm] ignored single char or filler noise: %s", u_clean)
            self.set_state(AgentState.LISTEN)
            return

        if should_skip_llm(user_prompt):
            speak = canned_reply_for(user_prompt) or persona_reply_for(user_prompt)
            LOG.info("[llm] fast-path (skip LLM): %s", speak[:48])
            await self._speak_turn(speak)
            return

        await self._prepare_llm_call()
        prompt = self._build_llm_prompt(user_prompt)
        LOG.info(
            "[llm] hist=%d/%d prompt %d chars · user=%s",
            len(self._chat_turns),
            self.history_max_turns,
            len(prompt),
            user_prompt[:48],
        )
        buffer = {"text": ""}
        loop = asyncio.get_running_loop()
        splitter = StreamingSentenceSplitter(min_clause_chars=8, max_clause_chars=22)
        tts_state: dict[str, int | bool] = {"n": 0, "canned": False}

        def on_token(piece: str) -> None:
            if self._tts_abort:
                return
            buffer["text"] += piece
            asyncio.run_coroutine_threadsafe(
                self.emit({"type": "llm_token", "text": piece}),
                loop,
            )
            chunks = splitter.feed(piece)
            for ch in chunks:
                if self._tts_abort:
                    break
                asyncio.run_coroutine_threadsafe(
                    self._enqueue_speak(ch, tts_state),
                    loop,
                )

        try:
            reply = await asyncio.to_thread(
                llm_chat_stream,
                prompt,
                on_token,
                sock_path=self.socket_path,
                max_new_tokens=self.max_new_tokens,
            )
            rem = splitter.finish()
            for ch in rem:
                if self._tts_abort:
                    break
                await self._enqueue_speak(ch, tts_state)

            full = clean_llm_reply(user_prompt, reply["text"])

            if int(tts_state["n"]) == 0 and not self._tts_abort:
                speak = persona_reply_for(user_prompt)
                LOG.info("[llm] persona fallback: %s", speak[:48])
                await self._speak_extracted(speak, canned=True)
                full = speak
            elif not self._tts_abort:
                try:
                    await self.tts_queue.wait_done()
                finally:
                    self._speaking = False

            if not self._tts_abort:
                self._listen_cooldown_until = time.monotonic() + self.listen_cooldown_sec
                if full.strip():
                    self._record_chat_turn(user_prompt, full)

            LOG.info(
                "[llm] reply (%d chars, ttft=%.3fs): %s",
                len(full),
                reply.get("ttft_s") or 0.0,
                full[:60],
            )
            if self._tts_abort:
                LOG.info("[barge-in] skipped post-abort cooldown")
        except OSError as exc:
            LOG.error("[llm] request failed: %s", exc)

    async def run(self, inject_wav: str | None = None) -> None:
        self._loop = asyncio.get_running_loop()
        (self.agent_root / "run").mkdir(parents=True, exist_ok=True)
        (self.agent_root / "logs").mkdir(parents=True, exist_ok=True)
        self.set_state(AgentState.IDLE)
        self.ping_llm_daemon()
        await self.tts_queue.start()
        if self.api_enabled:
            try:
                await run_ws_server(self.event_bus, self.api_host, self.api_port)
            except OSError as exc:
                LOG.warning(
                    "[api] WebSocket bind failed (%s) — voice pipeline continues without WS",
                    exc,
                )
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
