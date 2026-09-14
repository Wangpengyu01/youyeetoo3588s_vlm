from __future__ import annotations

import asyncio
import io
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from orchestrator.config_loader import load_yaml  # noqa: E402
from orchestrator.dialogue_policy import is_vision_query  # noqa: E402
from orchestrator.events import AgentState  # noqa: E402
from orchestrator.main import Orchestrator  # noqa: E402


class VisionTurnTests(unittest.IsolatedAsyncioTestCase):
    def test_camera_config_loaded(self) -> None:
        cfg = load_yaml(AGENT_ROOT / "config" / "agent.yaml")
        self.assertIn("camera", cfg)
        cam = cfg["camera"]
        self.assertTrue(cam.get("enabled"))
        self.assertIn("10.0.0.159:8080", cam.get("url", ""))

    def test_vision_intent_rules(self) -> None:
        positives = [
            "看看桌上有什么",
            "这是什么",
            "能看见我吗",
            "你帮我看看这是什么东西",
            "看下这个",
            "镜头前面有什么",
            "帮我拍个照看看",
            "摄像头能看清吗",
        ]
        for q in positives:
            self.assertTrue(is_vision_query(q), f"Should match vision query: {q}")

        negatives = [
            "今天天气怎么样",
            "中国的首都是哪里",
            "你在干什么呢",
            "讲个故事吧",
            "停",
            "继续",
            "小揽你在吗",
        ]
        for q in negatives:
            self.assertFalse(is_vision_query(q), f"Should NOT match vision query: {q}")

    async def test_vision_turn_speaks_caption_and_emits_events(self) -> None:
        orch = object.__new__(Orchestrator)
        orch.camera_enabled = True
        orch.camera_url = "http://fake-camera/shot.jpg"
        orch.camera_timeout = 1.0
        orch.camera_size = 448
        orch.camera_prompt = "描述画面"
        orch.camera_vlm_cmd = "/nonexistent/vlm_see.sh"
        orch.camera_api_url = ""
        orch.camera_api_key = ""
        orch.camera_model = "test"
        orch.agent_root = AGENT_ROOT
        orch._tts_abort = False
        orch._active_turn_id = 1
        orch._chat_turns = []
        orch.history_max_turns = 2
        orch.listen_cooldown_sec = 0.1
        orch.state = AgentState.LISTEN
        orch.set_state = lambda state: setattr(orch, "state", state)

        events: list[dict] = []
        spoken: list[tuple[str, int]] = []

        async def fake_emit(ev: dict) -> None:
            events.append(ev)

        async def fake_speak(text: str, *, generation: int) -> None:
            spoken.append((text, generation))

        orch.emit = fake_emit  # type: ignore[method-assign]
        orch._speak_turn = fake_speak  # type: ignore[method-assign]

        with patch.object(orch, "_grab_camera_frame", return_value=True),              patch.object(orch, "_prepare_vlm_frame", return_value=True),              patch.object(orch, "_infer_vlm", return_value="桌上放着一盒抽纸和一个白色水杯。"):
            await orch._run_llm("看看桌上放了什么", generation=1, vad_end_at=time.monotonic())

        self.assertEqual(len(spoken), 1)
        self.assertEqual(spoken[0][0], "桌上放着一盒抽纸和一个白色水杯。")
        self.assertEqual(spoken[0][1], 1)
        event_types = [e["type"] for e in events]
        self.assertIn("vision_start", event_types)
        self.assertIn("vision_caption", event_types)
        self.assertEqual(len(orch._chat_turns), 1)
        self.assertEqual(orch._chat_turns[0][0], "看看桌上放了什么")
        self.assertEqual(orch._chat_turns[0][1], "桌上放着一盒抽纸和一个白色水杯。")

    async def test_vision_turn_camera_offline_speaks_friendly_message(self) -> None:
        orch = object.__new__(Orchestrator)
        orch.camera_enabled = True
        orch.camera_url = "http://offline-camera/shot.jpg"
        orch.camera_timeout = 0.5
        orch.camera_size = 448
        orch.camera_prompt = "描述画面"
        orch.camera_vlm_cmd = "/nonexistent/vlm_see.sh"
        orch.camera_api_url = ""
        orch.camera_api_key = ""
        orch.camera_model = "test"
        orch.agent_root = AGENT_ROOT
        orch._tts_abort = False
        orch._active_turn_id = 2
        orch._chat_turns = []
        orch.history_max_turns = 2
        orch.listen_cooldown_sec = 0.1
        orch.state = AgentState.LISTEN
        orch.set_state = lambda state: setattr(orch, "state", state)

        events: list[dict] = []
        spoken: list[tuple[str, int]] = []

        async def fake_emit(ev: dict) -> None:
            events.append(ev)

        async def fake_speak(text: str, *, generation: int) -> None:
            spoken.append((text, generation))

        orch.emit = fake_emit  # type: ignore[method-assign]
        orch._speak_turn = fake_speak  # type: ignore[method-assign]

        with patch.object(orch, "_grab_camera_frame", return_value=False):
            await orch._run_llm("这是什么东西", generation=2, vad_end_at=time.monotonic())

        self.assertEqual(len(spoken), 1)
        self.assertIn("摄像头暂时连接不上", spoken[0][0])
        event_types = [e["type"] for e in events]
        self.assertIn("vision_error", event_types)

    async def test_non_vision_query_bypasses_camera(self) -> None:
        orch = object.__new__(Orchestrator)
        orch.camera_enabled = True
        orch.state = AgentState.LISTEN
        orch.set_state = lambda state: setattr(orch, "state", state)
        orch._tts_abort = False
        orch._active_turn_id = 3
        orch._chat_turns = []
        orch.history_max_turns = 0
        orch.system_prompt = ""
        orch.socket_path = "/ignored"
        orch.max_new_tokens = 64
        orch.listen_cooldown_sec = 0.1
        orch._speaking = False
        orch._active_tts_text = ""
        orch._last_spoken_turn = ""
        orch._last_tts_end_at = 0.0
        orch._listen_cooldown_until = 0.0
        orch._paused_relay_text = None
        orch._current_splitter = None
        orch.tts_queue = type("Queue", (), {
            "first_play_latency_s": 0.5,
            "first_play_at": 1.0,
            "enqueue": lambda self, text, **kwargs: asyncio.sleep(0),
            "wait_done": lambda self, **kwargs: asyncio.sleep(0),
        })()

        events: list[dict] = []
        spoken: list[tuple[str, int]] = []

        async def fake_emit(ev: dict) -> None:
            events.append(ev)

        async def fake_speak(text: str, *, generation: int) -> None:
            spoken.append((text, generation))

        orch.emit = fake_emit  # type: ignore[method-assign]
        orch._speak_turn = fake_speak  # type: ignore[method-assign]
        orch._prepare_llm_call = lambda: asyncio.sleep(0)  # type: ignore[method-assign]

        vision_called = False

        async def spy_vision(*args, **kwargs):
            nonlocal vision_called
            vision_called = True

        orch._handle_vision_turn = spy_vision  # type: ignore[method-assign]

        def fake_llm(prompt, on_token, **kwargs):
            on_token("中国的首都是北京。")
            return {"text": "中国的首都是北京。", "finish_reason": "stop"}

        with patch("orchestrator.main.llm_chat_stream", fake_llm):
            await orch._run_llm("中国的首都是哪里", generation=3, vad_end_at=time.monotonic())

        self.assertFalse(vision_called, "Vision pipeline should NOT be called for general knowledge query")


if __name__ == "__main__":
    unittest.main()
