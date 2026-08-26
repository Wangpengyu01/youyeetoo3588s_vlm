"""Async TTS queue — batch synth, single seamless play per utterance."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from tts.playback_prep import concat_wavs
from tts.sentence_split import is_speakable, sanitize_tts_text
from tts.tts_engine import TtsEngine

LOG = logging.getLogger(__name__)


class TtsQueue:
    def __init__(
        self,
        engine: TtsEngine,
        *,
        merge_max_chars: int = 80,
    ) -> None:
        self.engine = engine
        self.merge_max_chars = merge_max_chars  # kept for config compat
        self._text_q: asyncio.Queue[str | None] = asyncio.Queue()
        self._synth_task: asyncio.Task | None = None
        self._first_play_at: float | None = None
        self._utterance_started_at: float | None = None
        self._slot = 0
        self._interrupted = asyncio.Event()
        self._utterance_chunks = 0
        self._synth_done = 0
        self._batch_wavs: list[Path] = []

    @property
    def is_playing(self) -> bool:
        return self._text_q.qsize() > 0 or bool(self._batch_wavs)

    def set_max_sentences(self, n: int) -> None:
        _ = n

    async def discard_pending(self) -> None:
        self._batch_wavs.clear()
        self._synth_done = 0
        while True:
            try:
                self._text_q.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self._text_q.task_done()

    async def interrupt(self) -> None:
        self._interrupted.set()
        await self.discard_pending()
        await asyncio.to_thread(self.engine.stop_playback)
        LOG.info("[tts] interrupted")

    async def start(self) -> None:
        if self._synth_task is None:
            self._synth_task = asyncio.create_task(self._synth_worker())

    def mark_utterance_start(self) -> None:
        self._utterance_started_at = time.monotonic()
        self._first_play_at = None
        self._utterance_chunks = 0
        self._synth_done = 0
        self._batch_wavs.clear()
        self._interrupted.clear()

    @property
    def first_play_latency_s(self) -> float | None:
        if self._utterance_started_at is None or self._first_play_at is None:
            return None
        return self._first_play_at - self._utterance_started_at

    async def enqueue(self, text: str) -> None:
        if self._interrupted.is_set():
            return
        text = sanitize_tts_text(text)
        if not is_speakable(text):
            return
        self._utterance_chunks += 1
        await self._text_q.put(text)

    async def flush(self) -> None:
        return

    async def wait_done(self) -> None:
        if self._interrupted.is_set() or self._utterance_chunks <= 0:
            return
        await self._text_q.join()
        while self._synth_done < self._utterance_chunks and not self._interrupted.is_set():
            await asyncio.sleep(0.01)
        if self._interrupted.is_set() or not self._batch_wavs:
            return

        wavs = list(self._batch_wavs)
        self._batch_wavs.clear()
        self._synth_done = 0

        if len(wavs) == 1:
            play_wav = wavs[0]
            LOG.info("[tts] play plan: 1 chunk")
        else:
            play_wav = Path("/tmp/agent_tts_combined.wav")
            await asyncio.to_thread(concat_wavs, wavs, play_wav)
            LOG.info("[tts] play plan: %d chunks -> 1 seamless wav", len(wavs))

        self._first_play_at = time.monotonic()
        lat = self.first_play_latency_s
        if lat is not None:
            LOG.info("[tts] first_play latency=%.2fs", lat)

        t0 = time.monotonic()
        await asyncio.to_thread(
            self.engine.play,
            play_wav,
            last_in_utterance=True,
        )
        if not self._interrupted.is_set():
            LOG.info("[tts] play %.2fs (seamless)", time.monotonic() - t0)

    async def _synth_worker(self) -> None:
        while True:
            text = await self._text_q.get()
            try:
                if text is None:
                    return
                if self._interrupted.is_set():
                    continue
                path = Path(f"/tmp/agent_tts_{self._slot % 4}.wav")
                self._slot += 1
                t0 = time.monotonic()
                wav = await asyncio.to_thread(self.engine.synthesize, text, str(path))
                if self._interrupted.is_set():
                    continue
                LOG.info("[tts] synth %.2fs (%d chars)", time.monotonic() - t0, len(text))
                self._batch_wavs.append(wav)
                self._synth_done += 1
            except Exception as exc:
                LOG.error("[tts] synth failed: %s", exc)
                self._synth_done += 1
            finally:
                self._text_q.task_done()
