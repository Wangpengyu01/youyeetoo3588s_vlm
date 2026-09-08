from __future__ import annotations

import asyncio
import inspect
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
    def test_zero_history_omits_prior_turns_from_the_llm_prompt(self) -> None:
        orch = object.__new__(Orchestrator)
        orch.system_prompt = "只回答当前问题。"
        orch._chat_turns = [("走路还是开车", "你可以骑车。")]
        orch.history_max_turns = 0

        prompt = orch._build_llm_prompt("我要去洗车")

        self.assertEqual(
            prompt,
            "<|im_start|>system\n只回答当前问题。<|im_end|>\n"
            "<|im_start|>user\n我要去洗车<|im_end|>\n<|im_start|>assistant\n",
        )

    def test_zero_history_does_not_accumulate_transcript(self) -> None:
        orch = object.__new__(Orchestrator)
        orch._chat_turns = [("旧问题", "旧回答")]
        orch.history_max_turns = 0

        orch._record_chat_turn("新问题", "新回答")

        self.assertEqual(orch._chat_turns, [])

    def test_stream_loop_handles_the_asyncio_timeout_class_used_by_python_310(self) -> None:
        source = inspect.getsource(Orchestrator._run_llm)
        self.assertIn("except asyncio.TimeoutError:", source)

    async def test_llm_failure_speaks_a_short_recovery_prompt(self) -> None:
        orch = object.__new__(Orchestrator)
        orch._chat_turns = []
        orch.history_idle_clear_sec = 0
        orch.history_max_turns = 1
        orch.system_prompt = ""
        orch.socket_path = "/ignored"
        orch.max_new_tokens = 64
        orch._tts_abort = False
        orch._active_turn_id = 8
        orch._active_tts_text = ""
        orch._last_spoken_turn = ""
        orch._last_tts_end_at = 0.0
        orch._listen_cooldown_until = 0.0
        orch.listen_cooldown_sec = 0.2
        orch._paused_relay_text = None
        orch._current_splitter = None
        orch._speaking = False
        orch.state = AgentState.LLM
        events: list[dict] = []
        recovery: list[tuple[str, int]] = []

        async def emit(event: dict) -> None:
            events.append(event)

        async def prepare() -> None:
            return None

        async def speak(text: str, *, generation: int) -> None:
            recovery.append((text, generation))

        orch.emit = emit  # type: ignore[method-assign]
        orch._prepare_llm_call = prepare  # type: ignore[method-assign]
        orch._speak_turn = speak  # type: ignore[method-assign]
        orch.set_state = lambda state: None  # type: ignore[method-assign]

        def failing_stream(prompt: str, on_token, **kwargs):
            raise ConnectionResetError("llm socket reset")

        with patch("orchestrator.main.llm_chat_stream", failing_stream):
            await orch._run_llm("请解释一个复杂问题", generation=8, vad_end_at=time.monotonic())

        self.assertEqual(recovery, [("刚才出了点问题，请再说一遍。", 8)])
        self.assertIn({"type": "error", "code": "llm_failed"}, events)

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

    async def test_streaming_turn_suppresses_repeated_model_clauses_and_history(self) -> None:
        orch = object.__new__(Orchestrator)
        orch._chat_turns = []
        orch.history_idle_clear_sec = 0
        orch.history_max_turns = 1
        orch.system_prompt = ""
        orch.socket_path = "/ignored"
        orch.max_new_tokens = 64
        orch._tts_abort = False
        orch._active_turn_id = 9
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

        repeated = "第一段解释。第二段解释。第一段解释。第二段解释。"

        def fake_stream(prompt: str, on_token, **kwargs):
            on_token(repeated)
            return {"text": repeated, "ttft_s": 0.01}

        with patch("orchestrator.main.llm_chat_stream", fake_stream):
            await orch._run_llm("重复问题", generation=9, vad_end_at=time.monotonic())

        self.assertEqual(
            orch.tts_queue.enqueued,
            [("第一段解释。", 9), ("第二段解释。", 9)],
        )
        token_events = [event["text"] for event in events if event["type"] == "llm_token"]
        self.assertEqual(token_events, ["第一段解释。", "第二段解释。"])
        self.assertEqual(orch._chat_turns, [("重复问题", "第一段解释。第二段解释。")])


if __name__ == "__main__":
    unittest.main()
