"""Streaming ASR session — simulate partial + final with SenseVoice."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from asr.audio_util import float32_to_int16_bytes, write_wav_int16
from asr.sense_voice import SenseVoiceAsr, SenseVoiceConfig

LOG = logging.getLogger(__name__)

PartialCb = Callable[[str], Awaitable[None]]
FinalCb = Callable[[str, dict], Awaitable[None]]


@dataclass
class AsrEngineConfig:
    sense_voice: SenseVoiceConfig = field(default_factory=SenseVoiceConfig)
    sample_rate: int = 16000
    partial_interval_sec: float = 1.2
    partial_min_sec: float = 0.8
    partial_enabled: bool = True
    max_partials_per_utterance: int = 3
    min_duration_sec: float = 0.5
    utterance_wav: str = "/userdata/agent/run/last_utterance.wav"


class AsrEngine:
    def __init__(self, cfg: AsrEngineConfig) -> None:
        self.cfg = cfg
        self.recognizer = SenseVoiceAsr(cfg.sense_voice)
        self.utterance_path = Path(cfg.utterance_wav)

    def create_session(
        self,
        on_partial: PartialCb,
        on_final: FinalCb,
    ) -> StreamingAsrSession:
        return StreamingAsrSession(self, on_partial, on_final)


class StreamingAsrSession:
    def __init__(
        self,
        engine: AsrEngine,
        on_partial: PartialCb,
        on_final: FinalCb,
    ) -> None:
        self.engine = engine
        self.on_partial = on_partial
        self.on_final = on_final
        self._buffer: list[float] = []
        self._active = False
        self._last_partial_at = 0.0
        self._last_partial_text = ""
        self._partial_running = False
        self._partial_count = 0

    @property
    def buffer_sec(self) -> float:
        return len(self._buffer) / self.engine.cfg.sample_rate

    async def start(self) -> None:
        self._buffer.clear()
        self._active = True
        self._last_partial_at = time.monotonic()
        self._last_partial_text = ""
        self._partial_count = 0

    async def feed(self, samples: list[float]) -> None:
        if not self._active or not samples:
            return
        self._buffer.extend(samples)
        if self.engine.cfg.partial_enabled:
            asyncio.create_task(self._maybe_partial())

    async def cancel(self) -> None:
        self._active = False
        self._buffer.clear()

    async def finalize_samples(self, samples: list[float]) -> dict:
        self._buffer = list(samples)
        return await self.finalize()

    async def finalize(self) -> dict:
        cfg = self.engine.cfg
        duration = self.buffer_sec
        self._active = False
        if duration < cfg.min_duration_sec:
            result = {"status": "skipped", "reason": "too_short", "duration_sec": duration, "text": ""}
            await self.on_final("", result)
            return result

        pcm = float32_to_int16_bytes(self._buffer)
        self.engine.utterance_path.parent.mkdir(parents=True, exist_ok=True)
        write_wav_int16(self.engine.utterance_path, pcm, sample_rate=cfg.sample_rate)
        LOG.info("[asr] saved utterance %.2fs -> %s", duration, self.engine.utterance_path)

        text = await asyncio.to_thread(
            self.engine.recognizer.recognize_samples,
            self._buffer,
            cfg.sample_rate,
            boost=True,
            wav_path=self.engine.utterance_path,
        )
        text = text.strip()
        LOG.info("[asr] final: %s", text or "(empty)")
        result = {
            "status": "ok" if text else "empty",
            "duration_sec": duration,
            "wav": str(self.engine.utterance_path),
            "text": text,
        }
        await self.on_final(text, result)
        self._buffer.clear()
        return result

    async def _maybe_partial(self) -> None:
        cfg = self.engine.cfg
        if not cfg.partial_enabled:
            return
        if self._partial_running:
            return
        if self._partial_count >= cfg.max_partials_per_utterance:
            return
        if self.buffer_sec < cfg.partial_min_sec:
            return
        now = time.monotonic()
        if now - self._last_partial_at < cfg.partial_interval_sec:
            return

        self._partial_running = True
        self._last_partial_at = now
        buf_snapshot = list(self._buffer)
        try:
            text = await asyncio.to_thread(
                self.engine.recognizer.recognize_samples,
                buf_snapshot,
                cfg.sample_rate,
                boost=False,
            )
            text = text.strip()
            if text and text != self._last_partial_text:
                self._last_partial_text = text
                self._partial_count += 1
                LOG.info("[asr] partial: %s", text)
                await self.on_partial(text)
        finally:
            self._partial_running = False
