"""Streaming ASR session — SenseVoice offline or Paraformer online."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Protocol

from asr.audio_util import (
    clipped_sample_ratio,
    float32_peak_int16,
    float32_to_int16_bytes,
    limit_peak_float32,
    write_wav_int16,
)
from asr.sense_voice import SenseVoiceAsr, SenseVoiceConfig
from asr.sherpa_streaming_asr import StreamingParaformerConfig, StreamingParaformerRecognizer

LOG = logging.getLogger(__name__)

PartialCb = Callable[[str], Awaitable[None]]
FinalCb = Callable[[str, dict], Awaitable[None]]


class _AsrBackend(Protocol):
    def reset(self) -> None: ...

    def feed(self, samples: list[float], sample_rate: int) -> str: ...

    def finalize(self, samples: list[float], sample_rate: int) -> str: ...


@dataclass
class AsrEngineConfig:
    backend: str = "sense_voice"
    sense_voice: SenseVoiceConfig = field(default_factory=SenseVoiceConfig)
    streaming_paraformer: StreamingParaformerConfig = field(default_factory=StreamingParaformerConfig)
    sample_rate: int = 16000
    partial_interval_sec: float = 1.2
    partial_min_sec: float = 0.8
    partial_enabled: bool = True
    max_partials_per_utterance: int = 3
    min_duration_sec: float = 0.5
    utterance_wav: str = "/userdata/agent/run/last_utterance.wav"
    clip_peak_threshold: int = 30000
    clip_limit_ceiling: float = 0.85


class _SenseVoiceBackend:
    def __init__(self, recognizer: SenseVoiceAsr, sample_rate: int) -> None:
        self.recognizer = recognizer
        self.sample_rate = sample_rate
        self._buffer: list[float] = []

    def reset(self) -> None:
        self._buffer.clear()

    def feed(self, samples: list[float], sample_rate: int) -> str:
        self._buffer.extend(samples)
        return ""

    def finalize(self, samples: list[float], sample_rate: int) -> str:
        buf = list(samples) if samples else self._buffer
        if not buf:
            return ""
        return self.recognizer.recognize_samples(buf, sample_rate, boost=True).strip()


class _StreamingParaformerBackend:
    def __init__(self, recognizer: StreamingParaformerRecognizer, sample_rate: int) -> None:
        self.recognizer = recognizer
        self.sample_rate = sample_rate
        self._buffer: list[float] = []

    def reset(self) -> None:
        self._buffer.clear()
        self.recognizer.reset()

    def feed(self, samples: list[float], sample_rate: int) -> str:
        self._buffer.extend(samples)
        if not samples:
            return ""
        return self.recognizer.feed(samples, sample_rate).strip()

    def finalize(self, samples: list[float], sample_rate: int) -> str:
        buf = list(samples) if samples else self._buffer
        if buf:
            self.recognizer.reset()
            chunk = max(1, int(sample_rate * 0.2))
            for i in range(0, len(buf), chunk):
                self.recognizer.feed(buf[i : i + chunk], sample_rate)
        return self.recognizer.finalize().strip()


class AsrEngine:
    def __init__(self, cfg: AsrEngineConfig) -> None:
        self.cfg = cfg
        self.utterance_path = Path(cfg.utterance_wav)
        self.backend_name = cfg.backend.strip().lower()
        if self.backend_name == "streaming_paraformer":
            self._backend_impl: _AsrBackend = _StreamingParaformerBackend(
                StreamingParaformerRecognizer(cfg.streaming_paraformer),
                cfg.sample_rate,
            )
            LOG.info("[asr] backend=streaming_paraformer dir=%s", cfg.streaming_paraformer.model_dir)
        else:
            self._backend_impl = _SenseVoiceBackend(SenseVoiceAsr(cfg.sense_voice), cfg.sample_rate)
            LOG.info("[asr] backend=sense_voice dir=%s", cfg.sense_voice.model_dir)

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
        self._streaming = engine.backend_name == "streaming_paraformer"

    @property
    def buffer_sec(self) -> float:
        return len(self._buffer) / self.engine.cfg.sample_rate

    async def start(self) -> None:
        self._buffer.clear()
        self._active = True
        self._last_partial_at = time.monotonic()
        self._last_partial_text = ""
        self._partial_count = 0
        await asyncio.to_thread(self.engine._backend_impl.reset)

    async def feed(self, samples: list[float]) -> None:
        if not self._active or not samples:
            return
        self._buffer.extend(samples)
        if not self.engine.cfg.partial_enabled:
            return
        if self._streaming:
            await self._streaming_partial(samples)
        else:
            asyncio.create_task(self._maybe_partial_offline())

    async def cancel(self) -> None:
        self._active = False
        self._buffer.clear()
        await asyncio.to_thread(self.engine._backend_impl.reset)

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
            await asyncio.to_thread(self.engine._backend_impl.reset)
            return result

        pcm_buf = list(self._buffer)
        peak_i16 = float32_peak_int16(pcm_buf)
        clip_ratio = clipped_sample_ratio(pcm_buf, threshold=cfg.clip_peak_threshold)
        if peak_i16 >= cfg.clip_peak_threshold:
            pcm_buf, gain, peak_i16 = limit_peak_float32(
                pcm_buf,
                ceiling=cfg.clip_limit_ceiling,
            )
            LOG.warning(
                "[asr] clipped capture peak=%d (%.1f%% samples) · limit gain=%.2f — "
                "lower mic gain or speak slightly farther from mic",
                peak_i16,
                100.0 * clip_ratio,
                gain,
            )
        pcm = float32_to_int16_bytes(pcm_buf)
        self.engine.utterance_path.parent.mkdir(parents=True, exist_ok=True)
        write_wav_int16(self.engine.utterance_path, pcm, sample_rate=cfg.sample_rate)
        LOG.info("[asr] saved utterance %.2fs -> %s", duration, self.engine.utterance_path)

        t0 = time.monotonic()
        impl = self.engine._backend_impl
        if isinstance(impl, _SenseVoiceBackend):
            text = await asyncio.to_thread(
                impl.recognizer.recognize_samples,
                pcm_buf,
                cfg.sample_rate,
                boost=True,
                wav_path=self.engine.utterance_path,
            )
        else:
            text = await asyncio.to_thread(
                impl.finalize,
                pcm_buf,
                cfg.sample_rate,
            )
        asr_ms = int((time.monotonic() - t0) * 1000)
        text = text.strip()
        LOG.info("[asr] final (%dms): %s", asr_ms, text or "(empty)")
        result = {
            "status": "ok" if text else "empty",
            "duration_sec": duration,
            "wav": str(self.engine.utterance_path),
            "text": text,
            "asr_ms": asr_ms,
            "backend": self.engine.backend_name,
        }
        await self.on_final(text, result)
        self._buffer.clear()
        await asyncio.to_thread(self.engine._backend_impl.reset)
        return result

    async def _streaming_partial(self, samples: list[float]) -> None:
        cfg = self.engine.cfg
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
        try:
            text = await asyncio.to_thread(
                self.engine._backend_impl.feed,
                list(samples),
                cfg.sample_rate,
            )
            text = text.strip()
            if text and text != self._last_partial_text:
                self._last_partial_text = text
                self._partial_count += 1
                LOG.info("[asr] partial: %s", text)
                await self.on_partial(text)
        finally:
            self._partial_running = False

    async def _maybe_partial_offline(self) -> None:
        cfg = self.engine.cfg
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
            impl = self.engine._backend_impl
            if not isinstance(impl, _SenseVoiceBackend):
                return
            text = await asyncio.to_thread(
                impl.recognizer.recognize_samples,
                buf_snapshot,
                cfg.sample_rate,
                False,
            )
            text = text.strip()
            if text and text != self._last_partial_text:
                self._last_partial_text = text
                self._partial_count += 1
                LOG.info("[asr] partial: %s", text)
                await self.on_partial(text)
        finally:
            self._partial_running = False
