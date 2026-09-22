from __future__ import annotations

import asyncio
import sys
import threading
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from tts.tts_queue import TtsQueue  # noqa: E402


class BlockingFakeEngine:
    def __init__(self) -> None:
        self.synthesis_started = threading.Event()
        self.release_synthesis = threading.Event()
        self.played_texts: list[str] = []

    def synthesize(self, text: str, path: str) -> Path:
        if text == "旧回答":
            self.synthesis_started.set()
            self.release_synthesis.wait(timeout=2)
        return Path(path)

    def play(
        self,
        wav: Path,
        *,
        continuation: bool,
        last_in_utterance: bool,
        utterance_gain: float | None,
    ) -> float:
        self.played_texts.append("旧回答" if "_0" in wav.stem else "新回答")
        return 1.0

    def stop_playback(self) -> None:
        return None


class TtsQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_synthesis_cannot_play_after_a_new_generation_starts(self) -> None:
        engine = BlockingFakeEngine()
        queue = TtsQueue(engine)
        await queue.start()
        try:
            queue.mark_utterance_start(1)
            await queue.enqueue("旧回答", generation=1)
            self.assertTrue(await asyncio.to_thread(engine.synthesis_started.wait, 1))

            await queue.interrupt()
            queue.mark_utterance_start(2)
            await queue.enqueue("新回答", generation=2)
            engine.release_synthesis.set()

            await asyncio.wait_for(queue.wait_done(generation=2), timeout=1)
            self.assertEqual(engine.played_texts, ["新回答"])
        finally:
            engine.release_synthesis.set()
            await queue.stop()

    async def test_stop_is_idempotent(self) -> None:
        queue = TtsQueue(BlockingFakeEngine())
        await queue.start()
        await queue.stop()
        await queue.stop()
        self.assertIsNone(queue._synth_task)
        self.assertIsNone(queue._play_task)


if __name__ == "__main__":
    unittest.main()
