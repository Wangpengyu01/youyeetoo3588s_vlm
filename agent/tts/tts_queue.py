"""Async sentence TTS queue — synth/play pipeline with sentence merging."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path

from tts.sentence_split import is_speakable, sanitize_tts_text
from tts.tts_engine import TtsEngine

LOG = logging.getLogger(__name__)
_SENT_END = re.compile(r"[。！？!?]$")


class TtsQueue:
    def __init__(
        self,
        engine: TtsEngine,
        *,
        merge_max_chars: int = 80,
    ) -> None:
        self.engine = engine
        self.merge_max_chars = merge_max_chars
        self._text_q: asyncio.Queue[str | None] = asyncio.Queue()
        self._wav_q: asyncio.Queue[tuple[Path, str] | None] = asyncio.Queue(maxsize=2)
        self._synth_task: asyncio.Task | None = None
        self._play_task: asyncio.Task | None = None
        self._merge_buf = ""
        self._first_play_at: float | None = None
        self._utterance_started_at: float | None = None
        self._fast_play_enabled = False
        self._slot = 0
        self._max_sentences = 1
        self._sentences_queued = 0
        self._interrupted = asyncio.Event()

    @property
    def is_playing(self) -> bool:
        return self._play_task is not None and not self._interrupted.is_set() and (
            self._wav_q.qsize() > 0 or self._text_q.qsize() > 0 or self._merge_buf
        )

    def set_max_sentences(self, n: int) -> None:
        self._max_sentences = max(1, n)

    async def discard_pending(self) -> None:
        """Drop unsynth/unplayed sentences for this turn."""
        self._merge_buf = ""
        while True:
            try:
                self._text_q.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self._text_q.task_done()
        await self._drain_wav_queue()
        self._sentences_queued = 0

    async def _drain_wav_queue(self) -> None:
        while True:
            try:
                self._wav_q.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self._wav_q.task_done()

    async def interrupt(self) -> None:
        """Stop playback and drop pending synth/play (barge-in)."""
        self._interrupted.set()
        self._merge_buf = ""
        await self.discard_pending()
        await self._drain_wav_queue()
        await asyncio.to_thread(self.engine.stop_playback)
        LOG.info("[tts] interrupted")

    async def start(self) -> None:
        if self._synth_task is None:
            self._synth_task = asyncio.create_task(self._synth_worker())
            self._play_task = asyncio.create_task(self._play_worker())

    def mark_utterance_start(self) -> None:
        self._utterance_started_at = time.monotonic()
        self._first_play_at = None
        self._merge_buf = ""
        self._fast_play_enabled = False
        self._sentences_queued = 0
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
        if self._merge_buf and not self._merge_buf.endswith((" ", "，", "。")):
            self._merge_buf += " "
        self._merge_buf += text
        buf = self._merge_buf.strip()
        if len(buf) >= self.merge_max_chars:
            await self._text_q.put(buf)
            self._merge_buf = ""
            self._sentences_queued += 1
        elif len(buf) >= 12 and _SENT_END.search(buf):
            await self._text_q.put(buf)
            self._merge_buf = ""
            self._sentences_queued += 1

    async def flush(self) -> None:
        if self._interrupted.is_set():
            self._merge_buf = ""
            return
        rest = sanitize_tts_text(self._merge_buf)
        self._merge_buf = ""
        if not rest:
            return
        max_chars = self.engine.cfg.max_chars
        while rest and not self._interrupted.is_set():
            if len(rest) <= max_chars:
                await self._text_q.put(rest)
                self._sentences_queued += 1
                break
            cut = rest.rfind("。", 0, max_chars)
            if cut < max_chars // 2:
                cut = max_chars
            else:
                cut += 1
            chunk = rest[:cut].strip()
            rest = rest[cut:].strip()
            if chunk:
                await self._text_q.put(chunk)
                self._sentences_queued += 1

    async def wait_done(self) -> None:
        if self._interrupted.is_set():
            return
        await self.flush()
        if self._interrupted.is_set():
            return
        await self._text_q.join()
        if self._interrupted.is_set():
            return
        await self._wav_q.join()

    async def _synth_worker(self) -> None:
        while True:
            text = await self._text_q.get()
            try:
                if text is None:
                    await self._wav_q.put(None)
                    return
                if self._interrupted.is_set():
                    continue
                path = f"/tmp/agent_tts_{self._slot % 2}.wav"
                self._slot += 1
                t0 = time.monotonic()
                wav = await asyncio.to_thread(self.engine.synthesize, text, path)
                if self._interrupted.is_set():
                    continue
                LOG.info("[tts] synth %.2fs (%d chars)", time.monotonic() - t0, len(text))
                await self._wav_q.put((wav, text))
            except Exception as exc:
                LOG.error("[tts] synth failed: %s", exc)
            finally:
                self._text_q.task_done()

    async def _play_worker(self) -> None:
        while True:
            item = await self._wav_q.get()
            try:
                if item is None:
                    return
                if self._interrupted.is_set():
                    continue
                wav, text = item
                if self._first_play_at is None:
                    self._first_play_at = time.monotonic()
                    lat = self.first_play_latency_s
                    if lat is not None:
                        LOG.info("[tts] first_play latency=%.2fs", lat)
                fast = self._fast_play_enabled
                LOG.info("[tts] speak: %s", text[:80])
                t0 = time.monotonic()
                await asyncio.to_thread(self.engine.play, wav, fast=fast)
                if self._interrupted.is_set():
                    LOG.info("[tts] play aborted (barge-in)")
                else:
                    LOG.info("[tts] play %.2fs%s", time.monotonic() - t0, " fast" if fast else "")
                self._fast_play_enabled = True
            except Exception as exc:
                LOG.error("[tts] play failed: %s", exc)
            finally:
                self._wav_q.task_done()
