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
    async def test_final_stop_command_interrupts_active_tts(self) -> None:
        """A short stop command may arrive only at ASR finalization, not as a partial."""
        orch = object.__new__(Orchestrator)
        orch.barge_in_enabled = True
        orch._speaking = True
        orch._active_tts_text = "这是一段正在播放的回答。"
        orch._last_spoken_turn = ""
        orch.tts_queue = type("Queue", (), {"_current_speaking_chunk": "正在播放。"})()
        orch._asr_session = None
        interrupts: list[str] = []

        class CapturingAsrEngine:
            def create_session(self, on_partial, on_final):
                self.on_partial = on_partial
                self.on_final = on_final
                return object()

        engine = CapturingAsrEngine()
        orch.asr_engine = engine

        async def emit(event: dict) -> None:
            return None

        async def interrupt() -> None:
            interrupts.append("stop")

        orch.emit = emit  # type: ignore[method-assign]
        orch._interrupt_tts = interrupt  # type: ignore[method-assign]
        orch._new_asr_session()

        await engine.on_final("停", {})

        self.assertEqual(interrupts, ["stop"])

    async def test_single_non_echo_partial_interrupts_active_tts(self) -> None:
        """A user saying one distinct syllable must barge in before ASR finalizes."""
        orch = object.__new__(Orchestrator)
        orch.barge_in_enabled = True
        orch.barge_in_min_sec = 0.15
        orch._speaking = True
        orch._active_tts_text = "这是一段正在播放的回答。"
        orch._last_spoken_turn = ""
        orch.tts_queue = type("Queue", (), {"_current_speaking_chunk": "正在播放。"})()
        orch._asr_session = None
        interrupts: list[str] = []

        class Session:
            buffer_sec = 0.15

        class CapturingAsrEngine:
            def create_session(self, on_partial, on_final):
                self.on_partial = on_partial
                self.on_final = on_final
                return Session()

        engine = CapturingAsrEngine()
        orch.asr_engine = engine

        async def emit(event: dict) -> None:
            return None

        async def interrupt() -> None:
            interrupts.append("barge-in")

        orch.emit = emit  # type: ignore[method-assign]
        orch._interrupt_tts = interrupt  # type: ignore[method-assign]
        orch._new_asr_session()

        await engine.on_partial("喂")

        self.assertEqual(interrupts, ["barge-in"])

    async def test_speech_start_does_not_interrupt_tts_before_echo_is_classified(self) -> None:
        """A raw VAD onset can be the speaker itself and must not self-abort TTS."""
        orch = object.__new__(Orchestrator)
        orch.vad_queue = asyncio.Queue()
        orch._turn_queue = asyncio.Queue()
        orch._speaking = True
        orch._turn_busy = True
        orch._asr_session = None
        orch.barge_in_enabled = True
        orch.mute_mic_during_tts = False
        interrupts: list[str] = []

        async def interrupt() -> None:
            interrupts.append("vad-onset")
            orch._speaking = False

        def set_state(state) -> None:
            return None

        class Session:
            async def start(self) -> None:
                return None

        class AsrEngine:
            def create_session(self, on_partial, on_final):
                return Session()

        orch._interrupt_tts = interrupt  # type: ignore[method-assign]
        orch.set_state = set_state  # type: ignore[method-assign]
        orch.asr_engine = AsrEngine()
        await orch.vad_queue.put({"type": "speech_start"})
        await orch.vad_queue.put({"type": "shutdown"})

        await orch.handle_events()

        self.assertEqual(interrupts, [])

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

    async def test_streaming_turn_never_reprompts_after_a_length_limited_segment(self) -> None:
        """The RKNN session restarts on a fresh prompt, so it must not be asked to "continue"."""
        orch = object.__new__(Orchestrator)
        orch._chat_turns = []
        orch.history_idle_clear_sec = 0
        orch.history_max_turns = 0
        orch.system_prompt = "只用完整短句回答。"
        orch.socket_path = "/ignored"
        orch.max_new_tokens = 8
        orch._tts_abort = False
        orch._active_turn_id = 10
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

        async def emit(event: dict) -> None:
            return None

        async def prepare() -> None:
            return None

        orch.emit = emit  # type: ignore[method-assign]
        orch._prepare_llm_call = prepare  # type: ignore[method-assign]
        orch.set_state = lambda state: None  # type: ignore[method-assign]

        calls: list[str] = []

        def fake_stream(prompt: str, on_token, **kwargs):
            calls.append(prompt)
            if len(calls) > 1:
                raise AssertionError("a new prompt would restart the RKNN answer")
            on_token("第一段已经讲到这里。")
            return {"text": "第一段已经讲到这里。", "ttft_s": 0.01, "finish_reason": "length"}

        with patch("orchestrator.main.llm_chat_stream", fake_stream), patch(
            "orchestrator.main.llm_clear_history"
        ):
            await orch._run_llm("请完整解释这个复杂问题", generation=10, vad_end_at=time.monotonic())

        self.assertEqual(
            orch.tts_queue.enqueued,
            [("第一段已经讲到这里。", 10)],
        )
        self.assertEqual(len(calls), 1)

    async def test_streaming_turn_does_not_continue_on_a_normal_daemon_finish(self) -> None:
        """The daemon's completion state, not its diagnostic counter, decides continuation."""
        orch = object.__new__(Orchestrator)
        orch._chat_turns = []
        orch.history_idle_clear_sec = 0
        orch.history_max_turns = 0
        orch.system_prompt = "只用完整短句回答。"
        orch.socket_path = "/ignored"
        orch.max_new_tokens = 8
        orch._tts_abort = False
        orch._active_turn_id = 11
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

        async def emit(event: dict) -> None:
            return None

        async def prepare() -> None:
            return None

        orch.emit = emit  # type: ignore[method-assign]
        orch._prepare_llm_call = prepare  # type: ignore[method-assign]
        orch.set_state = lambda state: None  # type: ignore[method-assign]
        calls: list[str] = []

        def fake_stream(prompt: str, on_token, **kwargs):
            calls.append(prompt)
            on_token("这一段已经完整结束。")
            return {
                "text": "这一段已经完整结束。",
                "ttft_s": 0.01,
                "finish_reason": "stop",
                "usage": {"tokens": 8192},
            }

        with patch("orchestrator.main.llm_chat_stream", fake_stream), patch(
            "orchestrator.main.llm_clear_history"
        ):
            await orch._run_llm("请解释这个复杂问题", generation=11, vad_end_at=time.monotonic())

        self.assertEqual(orch.tts_queue.enqueued, [("这一段已经完整结束。", 11)])
        self.assertEqual(len(calls), 1)

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
