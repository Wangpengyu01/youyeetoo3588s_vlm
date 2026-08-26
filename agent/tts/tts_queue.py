"""Async sentence TTS queue — synth/play pipeline with sentence merging."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path

from tts.sentence_split import sanitize_tts_text
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

    async def start(self) -> None:
        if self._synth_task is None:
            self._synth_task = asyncio.create_task(self._synth_worker())
            self._play_task = asyncio.create_task(self._play_worker())

    def mark_utterance_start(self) -> None:
        self._utterance_started_at = time.monotonic()
        self._first_play_at = None
        self._merge_buf = ""
        self._fast_play_enabled = False

    @property
    def first_play_latency_s(self) -> float | None:
        if self._utterance_started_at is None or self._first_play_at is None:
            return None
        return self._first_play_at - self._utterance_started_at

    async def enqueue(self, text: str) -> None:
        text = sanitize_tts_text(text)
        if not text:
            return
        if self._merge_buf and not self._merge_buf.endswith((" ", "，", "。")):
            self._merge_buf += " "
        self._merge_buf += text
        buf = self._merge_buf.strip()
        if len(buf) >= self.merge_max_chars:
            await self._text_q.put(buf)
            self._merge_buf = ""
        elif len(buf) >= 12 and _SENT_END.search(buf):
            await self._text_q.put(buf)
            self._merge_buf = ""

    async def flush(self) -> None:
        rest = sanitize_tts_text(self._merge_buf)
        self._merge_buf = ""
        if not rest:
            return
        max_chars = self.engine.cfg.max_chars
        while rest:
            if len(rest) <= max_chars:
                await self._text_q.put(rest)
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

    async def wait_done(self) -> None:
        await self.flush()
        await self._text_q.join()
        await self._wav_q.join()

    async def _synth_worker(self) -> None:
        while True:
            text = await self._text_q.get()
            try:
                if text is None:
                    await self._wav_q.put(None)
                    return
                path = f"/tmp/agent_tts_{self._slot % 2}.wav"
                self._slot += 1
                t0 = time.monotonic()
                wav = await asyncio.to_thread(self.engine.synthesize, text, path)
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
                LOG.info("[tts] play %.2fs%s", time.monotonic() - t0, " fast" if fast else "")
                self._fast_play_enabled = True
            except Exception as exc:
                LOG.error("[tts] play failed: %s", exc)
            finally:
                self._wav_q.task_done()
