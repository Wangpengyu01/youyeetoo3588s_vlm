"""Async sentence TTS queue — synth + play sequentially."""
from __future__ import annotations

import asyncio
import logging
import time

from tts.tts_engine import TtsEngine

LOG = logging.getLogger(__name__)


class TtsQueue:
    def __init__(self, engine: TtsEngine) -> None:
        self.engine = engine
        self._q: asyncio.Queue[str | None] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._first_play_at: float | None = None
        self._utterance_started_at: float | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._worker())

    def mark_utterance_start(self) -> None:
        self._utterance_started_at = time.monotonic()
        self._first_play_at = None

    @property
    def first_play_latency_s(self) -> float | None:
        if self._utterance_started_at is None or self._first_play_at is None:
            return None
        return self._first_play_at - self._utterance_started_at

    async def enqueue(self, text: str) -> None:
        text = text.strip()
        if text:
            await self._q.put(text)

    async def wait_done(self) -> None:
        await self._q.join()

    async def _worker(self) -> None:
        while True:
            text = await self._q.get()
            try:
                if text is None:
                    return
                if self._first_play_at is None:
                    self._first_play_at = time.monotonic()
                    lat = self.first_play_latency_s
                    if lat is not None:
                        LOG.info("[tts] first_play latency=%.2fs", lat)
                await asyncio.to_thread(self.engine.speak, text)
            except Exception as exc:
                LOG.error("[tts] failed: %s", exc)
            finally:
                self._q.task_done()
