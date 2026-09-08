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
from orchestrator.dialogue_policy import (
    can_barge_in,
    is_resume_command,
    is_stop_command,
    normalize_spoken_text,
)
from orchestrator.events import AgentState
from tts.sentence_split import (
    StreamingSentenceSplitter,
    canned_reply_for,
    clean_llm_reply,
    extract_speak_sentences,
    is_echo_reply,
    is_self_echo,
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
        self._turn_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=2)
        self._asr_session = None
        self._listen_cooldown_until = 0.0
        self._turn_busy = False
        self._speaking = False
        self._tts_abort = False
        self._active_tts_text = ""
        self._last_spoken_turn = ""
        self._last_tts_end_at = 0.0
        self._paused_relay_text: str | None = None
        self._current_splitter: Any = None
        self._next_turn_id = 0
        self._active_turn_id = 0
        self._ws_server: asyncio.Server | None = None

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
        self.mute_mic_during_tts = str(vad_cfg.get("mute_mic_during_tts", "false")).lower() not in ("0", "false", "no")

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
        session: Any = None
        last_partial = ""

        async def on_partial(text: str) -> None:
            nonlocal last_partial
            LOG.info("[event] asr_partial: %s", text)
            await self.emit({"type": "asr_partial", "text": text})
            if self.barge_in_enabled and self._speaking and text.strip():
                clean_p = normalize_spoken_text(text)
                if not clean_p:
                    return
                cur_speak = (
                    (self._active_tts_text or "")
                    + " "
                    + (getattr(self.tts_queue, "_current_speaking_chunk", "") or "")
                    + " "
                    + (self._last_spoken_turn or "")
                ).strip()
                if cur_speak and is_self_echo(cur_speak, clean_p):
                    LOG.info("[barge-in] self-acoustic feedback detected: %s", clean_p[:15])
                    return
                if is_stop_command(clean_p):
                    LOG.info("[barge-in] stop command matched: %s", clean_p)
                    await self._interrupt_tts()
                    return
                speech_sec = session.buffer_sec if session is not None else 0.0
                if not can_barge_in(clean_p, speech_sec, self.barge_in_min_sec):
                    return
                if clean_p.startswith(last_partial) and len(clean_p) > len(last_partial):
                    delta = clean_p[len(last_partial) :]
                else:
                    delta = clean_p[-4:]
                last_partial = clean_p
                if delta and cur_speak and is_self_echo(cur_speak, delta):
                    LOG.info("[barge-in] self-acoustic feedback delta ignored: %s", delta)
                    return
                LOG.info("[barge-in] user speech after %.2fs, interrupting TTS: %s", speech_sec, text)
                await self._interrupt_tts()

        async def on_final(text: str, meta: dict) -> None:
            LOG.info("[event] asr_final: %s", text or meta.get("status"))
            await self.emit({"type": "asr_final", "text": text, "meta": meta})

        session = self.asr_engine.create_session(on_partial, on_final)
        self._asr_session = session
        return session

    async def _interrupt_tts(self) -> None:
        if not self._speaking:
            return
        LOG.info("[barge-in] interrupt TTS playback immediately")
        self._tts_abort = True
        self._speaking = False
        self._last_tts_end_at = time.monotonic()
        self._listen_cooldown_until = 0.0
        pending = await self.tts_queue.interrupt()
        relay_parts = list(pending)
        if getattr(self, "_current_splitter", None):
            rem = self._current_splitter.finish()
            for r in rem:
                if r not in relay_parts:
                    relay_parts.append(r)
        if relay_parts:
            self._paused_relay_text = "".join(relay_parts).strip()
            LOG.info("[relay] saved %d pending clauses (%d chars) for resume: %s", len(relay_parts), len(self._paused_relay_text), self._paused_relay_text[:40])
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
                if event is None:
                    LOG.info("[turn] worker shutdown")
                    return
                await self._process_turn(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("[turn] processing failed")
                self._speaking = False
                self._tts_abort = False
                self.set_state(AgentState.LISTEN)
                await self.emit({"type": "error", "code": "turn_failed"})
            finally:
                self._turn_queue.task_done()

    async def _enqueue_turn(self, event: dict[str, Any]) -> None:
        """Keep the newest speech turns instead of answering an obsolete backlog."""
        event.setdefault("_vad_end_at", time.monotonic())
        dropped = 0
        while self._turn_queue.full():
            stale = self._turn_queue.get_nowait()
            self._turn_queue.task_done()
            if stale is None:
                await self._turn_queue.put(None)
                return
            dropped += 1
        if dropped:
            LOG.info("[turn] dropped %d stale queued segment(s)", dropped)
        await self._turn_queue.put(event)

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
            if self.mute_mic_during_tts and self._speaking:
                if self._asr_session:
                    await self._asr_session.cancel()
                    self._asr_session = None
                LOG.debug("[vad] half-duplex diagnostic mode dropped %s", etype)
                continue
            if etype == "speech_start":
                if self._turn_busy and not self._speaking:
                    LOG.debug("[vad] ignore speech start while ASR/LLM owns recognizer")
                    continue
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
                    if duration >= self.barge_in_min_sec:
                        LOG.info("[vad] speaking turn, queuing potential user speech (%.2fs)", duration)
                        await self._enqueue_turn(event)
                    continue
                if self._turn_busy and not self._speaking and not self._tts_abort:
                    if duration >= 0.8:
                        LOG.info("[vad] busy turn, but segment is valid user speech (%.2fs), queuing", duration)
                        await self._enqueue_turn(event)
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
                await self._enqueue_turn(event)
        await self._turn_queue.put(None)

    async def _process_turn(self, event: dict[str, Any]) -> None:
        self._next_turn_id += 1
        generation = self._next_turn_id
        self._active_turn_id = generation
        self._turn_busy = True
        self._tts_abort = False
        self.tts_queue.mark_utterance_start(generation)
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
                recent_tts = self._speaking or (time.monotonic() - getattr(self, "_last_tts_end_at", 0.0) < 2.0)
                cur_speak = (
                    (getattr(self, "_active_tts_text", "") or "")
                    + " "
                    + (getattr(self, "_last_spoken_turn", "") or "")
                ).strip()
                if recent_tts and cur_speak and is_self_echo(cur_speak, text):
                    LOG.warning(
                        "[asr] detected acoustic echo of assistant speech ('%s' in '%s'), dropping loop",
                        text,
                        cur_speak[:30],
                    )
                    return
                await self._run_llm(
                    text,
                    generation=generation,
                    vad_end_at=float(event.get("_vad_end_at", time.monotonic())),
                )
            else:
                LOG.info("[asr] no text recognized")
        finally:
            if self._asr_session is session:
                self._asr_session = None
            self._speaking = False
            self._turn_busy = False
            self.set_state(AgentState.LISTEN)

    async def _enqueue_speak(
        self,
        text: str,
        tts_state: dict[str, Any],
        *,
        generation: int,
    ) -> bool | None:
        if self._tts_abort or generation != self._active_turn_id:
            return False
        speak = sanitize_tts_text(text)
        if not is_speakable(speak):
            return False
        spoken_key = normalize_spoken_text(speak)
        spoken_keys: set[str] = tts_state.setdefault("spoken_keys", set())
        if spoken_key and spoken_key in spoken_keys:
            LOG.warning("[llm] suppressed repeated streamed clause: %s", speak[:60])
            return None
        if spoken_key:
            spoken_keys.add(spoken_key)
        tts_state["n"] = int(tts_state["n"]) + 1
        spoken_texts: list[str] = tts_state.setdefault("spoken_texts", [])
        spoken_texts.append(speak)
        if self.state != AgentState.TTS:
            self.set_state(AgentState.TTS)
        self._speaking = True
        LOG.info("[event] tts_sentence: %s", speak[:60])
        await self.emit({"type": "tts_sentence", "text": speak})
        await self.tts_queue.enqueue(speak, generation=generation)
        return True

    async def _speak_extracted(self, full: str, *, canned: bool = False, generation: int) -> None:
        """Enqueue every complete sentence in full — no char/sentence cap."""
        tts_state: dict[str, Any] = {"n": 0, "canned": canned, "spoken_keys": set(), "spoken_texts": []}
        sents = extract_speak_sentences(full, max_cjk=99999)
        if not sents:
            return
        LOG.info("[tts] speak plan: %d sentence(s)", len(sents))
        self._active_tts_text = full
        self._last_spoken_turn = full
        for sent in sents:
            if (await self._enqueue_speak(sent, tts_state, generation=generation)) is False:
                break
        if int(tts_state["n"]) <= 0 or self._tts_abort:
            return
        self.set_state(AgentState.TTS)
        self._speaking = True
        try:
            await self.tts_queue.wait_done(generation=generation)
        finally:
            self._speaking = False
            self._last_tts_end_at = time.monotonic()
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
        if self.history_max_turns > 0:
            for user, assistant in self._chat_turns[-self.history_max_turns :]:
                prompt += f"<|im_start|>user\n{user.strip()}<|im_end|>\n<|im_start|>assistant\n{assistant.strip()}<|im_end|>\n"
        prompt += f"<|im_start|>user\n{user_text.strip()}<|im_end|>\n<|im_start|>assistant\n"
        return prompt

    def _record_chat_turn(self, user: str, assistant: str) -> None:
        if self.history_max_turns <= 0:
            self._chat_turns.clear()
            return
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

    async def _speak_turn(self, text: str, *, generation: int) -> None:
        await self._speak_extracted(text, canned=True, generation=generation)

    async def _run_llm(self, prompt: str, *, generation: int, vad_end_at: float) -> None:
        user_prompt = prompt
        self.set_state(AgentState.LLM)

        u_clean = user_prompt.strip()
        normalized = normalize_spoken_text(u_clean)

        if is_resume_command(normalized):
            if getattr(self, "_paused_relay_text", None):
                relay = self._paused_relay_text
                self._paused_relay_text = None
                LOG.info("[relay] resuming playback from paused sentences (%d chars): %s", len(relay), relay[:60])
                await self._speak_turn(relay, generation=generation)
                return
            elif not self._chat_turns:
                await self._speak_turn("在呢，请问有什么想让我讲的吗？", generation=generation)
                return

        if is_stop_command(normalized):
            self._paused_relay_text = None
            LOG.info("[llm] user requested stop: %s", u_clean)
            await self._speak_turn("好的。", generation=generation)
            return

        self._paused_relay_text = None

        if len(normalized) <= 1 or (normalized and set(normalized) <= set("啊嗯呃哦呀吧呵哈嘿")):
            LOG.info("[llm] ignored single char or filler noise: %s", u_clean)
            self.set_state(AgentState.LISTEN)
            return

        if should_skip_llm(user_prompt):
            speak = canned_reply_for(user_prompt) or persona_reply_for(user_prompt)
            LOG.info("[llm] fast-path (skip LLM): %s", speak[:48])
            await self._speak_turn(speak, generation=generation)
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
        self._active_tts_text = ""
        loop = asyncio.get_running_loop()
        token_queue: asyncio.Queue[str] = asyncio.Queue()
        splitter = StreamingSentenceSplitter(min_clause_chars=7, max_clause_chars=26)
        self._current_splitter = splitter
        tts_state: dict[str, Any] = {"n": 0, "canned": False, "spoken_keys": set(), "spoken_texts": []}
        first_token_at: float | None = None

        def on_token(piece: str) -> None:
            loop.call_soon_threadsafe(token_queue.put_nowait, piece)

        try:
            llm_task = asyncio.create_task(
                asyncio.to_thread(
                    llm_chat_stream,
                    prompt,
                    on_token,
                    sock_path=self.socket_path,
                    max_new_tokens=self.max_new_tokens,
                )
            )

            while not llm_task.done() or not token_queue.empty():
                try:
                    piece = await asyncio.wait_for(token_queue.get(), timeout=0.04)
                except asyncio.TimeoutError:
                    continue
                if self._tts_abort or generation != self._active_turn_id:
                    continue
                if first_token_at is None:
                    first_token_at = time.monotonic()
                self._active_tts_text += piece
                for chunk in splitter.feed(piece):
                    if is_echo_reply(user_prompt, chunk):
                        LOG.warning("[llm] suppressed echo chunk: %s", chunk)
                        continue
                    queued = await self._enqueue_speak(chunk, tts_state, generation=generation)
                    if queued:
                        await self.emit({"type": "llm_token", "text": chunk})

            reply = await llm_task
            if not self._tts_abort and generation == self._active_turn_id:
                for chunk in splitter.finish():
                    if is_echo_reply(user_prompt, chunk):
                        LOG.warning("[llm] suppressed echo chunk: %s", chunk)
                        continue
                    queued = await self._enqueue_speak(chunk, tts_state, generation=generation)
                    if queued:
                        await self.emit({"type": "llm_token", "text": chunk})

            full = clean_llm_reply(user_prompt, reply["text"])

            if is_echo_reply(user_prompt, full):
                LOG.warning("[llm] detected echo reply ('%s' -> '%s'), wiping history", user_prompt, full)
                self._chat_turns.clear()
                full = "我没有听清楚，请再说一遍。"
                if int(tts_state["n"]) == 0 and not self._tts_abort:
                    await self._speak_extracted(full, canned=True, generation=generation)

            spoken_texts: list[str] = tts_state["spoken_texts"]
            if spoken_texts:
                full = "".join(spoken_texts)
                self._active_tts_text = full

            self._last_spoken_turn = full

            if int(tts_state["n"]) == 0 and not self._tts_abort:
                speak = persona_reply_for(user_prompt)
                LOG.info("[llm] persona fallback: %s", speak[:48])
                await self._speak_extracted(speak, canned=True, generation=generation)
                full = speak
                self._last_spoken_turn = full
            elif not self._tts_abort:
                try:
                    await self.tts_queue.wait_done(generation=generation)
                finally:
                    self._speaking = False
                    self._last_tts_end_at = time.monotonic()

            if not self._tts_abort:
                self._listen_cooldown_until = time.monotonic() + self.listen_cooldown_sec
                if full.strip():
                    self._record_chat_turn(user_prompt, full)

            first_play_at = self.tts_queue.first_play_at
            if first_play_at is not None:
                latency = {
                    "type": "latency",
                    "generation": generation,
                    "vad_to_first_token_ms": round(
                        1000 * ((first_token_at or first_play_at) - vad_end_at), 1
                    ),
                    "vad_to_first_play_ms": round(1000 * (first_play_at - vad_end_at), 1),
                }
                await self.emit(latency)
                LOG.info("[latency] turn=%d first_token=%sms first_play=%sms", generation, latency["vad_to_first_token_ms"], latency["vad_to_first_play_ms"])

            LOG.info(
                "[llm] reply (%d chars, ttft=%.3fs): %s",
                len(full),
                reply.get("ttft_s") or 0.0,
                full[:60],
            )
            if self._tts_abort:
                LOG.info("[barge-in] skipped post-abort cooldown")
        except Exception as exc:
            LOG.exception("[llm] request failed (%s): %r", type(exc).__name__, exc)
            await self.emit({"type": "error", "code": "llm_failed"})
            if not self._tts_abort and generation == self._active_turn_id:
                try:
                    await self._speak_turn("刚才出了点问题，请再说一遍。", generation=generation)
                except Exception:
                    LOG.exception("[tts] recovery prompt failed")
        finally:
            self._current_splitter = None

    async def run(self, inject_wav: str | None = None) -> None:
        self._loop = asyncio.get_running_loop()
        (self.agent_root / "run").mkdir(parents=True, exist_ok=True)
        (self.agent_root / "logs").mkdir(parents=True, exist_ok=True)
        self.set_state(AgentState.IDLE)
        self.ping_llm_daemon()
        await self.tts_queue.start()
        try:
            if self.api_enabled:
                try:
                    self._ws_server = await run_ws_server(self.event_bus, self.api_host, self.api_port)
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
        finally:
            if self._ws_server is not None:
                self._ws_server.close()
                await self._ws_server.wait_closed()
                self._ws_server = None
            await self.tts_queue.stop()


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
        async def _noop_enqueue(text: str, *, generation: int | None = None) -> None:
            LOG.info("[tts] skipped: %s", text[:60])

        async def _noop_wait(generation: int | None = None) -> None:
            return None

        orch.tts_queue.enqueue = _noop_enqueue  # type: ignore[method-assign]
        orch.tts_queue.wait_done = _noop_wait  # type: ignore[method-assign]
    try:
        asyncio.run(orch.run(inject_wav=args.inject_wav))
    except KeyboardInterrupt:
        LOG.info("stopped")


if __name__ == "__main__":
    main()
