"""Always-on mic + Silero VAD event stream."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from asr.audio_util import int16_bytes_to_float32, read_wav_float32
from asr.mic_capture import arm_mic, mic_route_guard, open_arecord
from asr.sherpa_vad import SherpaVad, SherpaVadError

LOG = logging.getLogger(__name__)


@dataclass
class VadConfig:
    model_path: str
    sherpa_lib: str
    sample_rate: int = 16000
    chunk_ms: int = 100
    threshold: float = 0.5
    min_silence_duration: float = 0.4
    min_speech_duration: float = 0.25
    max_speech_duration: float = 30.0
    alsa_device: str = "plughw:0,0"
    min_segment_sec: float = 0.5

    @property
    def chunk_samples(self) -> int:
        return int(self.sample_rate * self.chunk_ms / 1000)


class VadStream:
    """Feed mic PCM into sherpa Silero VAD; push events to asyncio.Queue."""

    def __init__(self, cfg: VadConfig, queue: asyncio.Queue[Any]) -> None:
        self.cfg = cfg
        self.queue = queue
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_live(self) -> None:
        arm_mic()
        guard_stop = asyncio.Event()
        guard_task = asyncio.create_task(mic_route_guard(guard_stop))
        proc = await open_arecord(device=self.cfg.alsa_device, sample_rate=self.cfg.sample_rate)
        try:
            await self._consume_arecord(proc)
        finally:
            guard_stop.set()
            await guard_task
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()

    async def run_wav_file(self, wav_path: str) -> None:
        samples, rate = read_wav_float32(wav_path)
        if rate != self.cfg.sample_rate:
            raise ValueError(f"expected {self.cfg.sample_rate} Hz wav, got {rate}")
        chunk = self.cfg.chunk_samples
        with SherpaVad(
            self.cfg.model_path,
            self.cfg.sherpa_lib,
            sample_rate=self.cfg.sample_rate,
            threshold=self.cfg.threshold,
            min_silence_duration=self.cfg.min_silence_duration,
            min_speech_duration=self.cfg.min_speech_duration,
            max_speech_duration=self.cfg.max_speech_duration,
        ) as vad:
            for i in range(0, len(samples), chunk):
                if self._stop.is_set():
                    break
                vad.accept_pcm_float32(samples[i : i + chunk])
                if vad.is_speech_detected:
                    await self.queue.put({"type": "audio_chunk", "samples": samples[i : i + chunk]})
                await self._emit(vad.poll_segments())
                await asyncio.sleep(self.cfg.chunk_ms / 1000.0)
            vad.flush()
            await self._emit(vad.poll_segments())

    async def _consume_arecord(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        chunk_bytes = self.cfg.chunk_samples * 2
        try:
            with SherpaVad(
                self.cfg.model_path,
                self.cfg.sherpa_lib,
                sample_rate=self.cfg.sample_rate,
                threshold=self.cfg.threshold,
                min_silence_duration=self.cfg.min_silence_duration,
                min_speech_duration=self.cfg.min_speech_duration,
                max_speech_duration=self.cfg.max_speech_duration,
            ) as vad:
                LOG.info("[vad] listening on %s", self.cfg.alsa_device)
                while not self._stop.is_set():
                    raw = await proc.stdout.read(chunk_bytes)
                    if not raw:
                        err = await proc.stderr.read() if proc.stderr else b""
                        if err:
                            LOG.error("[vad] arecord ended: %s", err.decode(errors="replace"))
                        break
                    floats = int16_bytes_to_float32(raw)
                    vad.accept_pcm_float32(floats)
                    if vad.is_speech_detected:
                        await self.queue.put({"type": "audio_chunk", "samples": floats})
                    await self._emit(vad.poll_segments())
        except SherpaVadError as exc:
            LOG.error("[vad] init failed: %s", exc)
            await self.queue.put({"type": "error", "source": "vad", "message": str(exc)})

    async def _emit(self, events: list[tuple[str, Any]]) -> None:
        for kind, payload in events:
            if kind == "speech_start":
                await self.queue.put({"type": "speech_start"})
            elif kind == "speech_end":
                await self.queue.put({"type": "speech_end"})
            elif kind == "segment" and payload is not None:
                if payload.duration_sec < self.cfg.min_segment_sec:
                    LOG.debug("[vad] drop short segment %.2fs", payload.duration_sec)
                    continue
                await self.queue.put(
                    {
                        "type": "audio_segment",
                        "samples": payload.samples,
                        "duration_sec": payload.duration_sec,
                        "start": payload.start,
                    }
                )
