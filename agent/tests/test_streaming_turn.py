from __future__ import annotations

import asyncio
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from orchestrator.main import Orchestrator  # noqa: E402
from orchestrator.events import AgentState  # noqa: E402


class FakeTtsQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, int]] = []
        self.first_play_at: float | None = None

    async def enqueue(self, text: str, *, generation: int) -> None:
        self.enqueued.append((text, generation))

    async def wait_done(self, *, generation: int) -> None:
        self.first_play_at = time.monotonic()


class StreamingTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_streaming_turn_hides_thinking_and_enqueues_a_natural_clause(self) -> None:
        orch = object.__new__(Orchestrator)
        orch._chat_turns = []
        orch.history_idle_clear_sec = 0
        orch.history_max_turns = 1
        orch.system_prompt = ""
        orch.socket_path = "/ignored"
        orch.max_new_tokens = 64
        orch._tts_abort = False
        orch._active_turn_id = 7
        orch._active_tts_text = ""
        orch._last_spoken_turn = ""
        orch._last_tts_end_at = 0.0
        orch._listen_cooldown_until = 0.0
        orch.listen_cooldown_sec = 0.2
        orch._paused_relay_text = None
        orch._current_splitter = None
        orch._speaking = False
        orch.state = AgentState.LLM
        orch.tts_queue = FakeTtsQueue()
        events: list[dict] = []

        async def emit(event: dict) -> None:
            events.append(event)

        async def prepare() -> None:
            return None

        orch.emit = emit  # type: ignore[method-assign]
        orch._prepare_llm_call = prepare  # type: ignore[method-assign]
        orch.set_state = lambda state: None  # type: ignore[method-assign]

        def fake_stream(prompt: str, on_token, **kwargs):
            on_token("<think>secret</think>")
            on_token("第一句可以立刻说，")
            on_token("第二句随后继续。")
            return {
                "text": "<think>secret</think>第一句可以立刻说，第二句随后继续。",
                "ttft_s": 0.01,
            }

        with patch("orchestrator.main.llm_chat_stream", fake_stream):
            await orch._run_llm("请解释一个复杂问题", generation=7, vad_end_at=time.monotonic())

        self.assertEqual(
            orch.tts_queue.enqueued,
            [("第一句可以立刻说，", 7), ("第二句随后继续。", 7)],
        )
        token_events = [event for event in events if event["type"] == "llm_token"]
        self.assertTrue(token_events)
        self.assertNotIn("secret", "".join(event["text"] for event in token_events))
        self.assertTrue(any(event["type"] == "latency" for event in events))


if __name__ == "__main__":
    unittest.main()
