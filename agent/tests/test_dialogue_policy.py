from __future__ import annotations

import sys
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from orchestrator.dialogue_policy import (  # noqa: E402
    can_barge_in,
    is_resume_command,
    is_stop_command,
)


class DialoguePolicyTests(unittest.TestCase):
    def test_stop_command_requires_a_complete_command(self) -> None:
        self.assertTrue(is_stop_command("停"))
        self.assertTrue(is_stop_command("别说了"))
        self.assertFalse(is_stop_command("停车场在哪里"))
        self.assertFalse(is_stop_command("停止服务后怎么重启"))

    def test_resume_command_requires_a_complete_command(self) -> None:
        self.assertTrue(is_resume_command("继续"))
        self.assertTrue(is_resume_command("你接着说吧"))
        self.assertFalse(is_resume_command("继续教育怎么报名"))

    def test_barge_in_waits_for_configured_speech_duration(self) -> None:
        self.assertFalse(can_barge_in("喂", 0.14, 0.15))
        self.assertFalse(can_barge_in("", 0.40, 0.15))
        self.assertTrue(can_barge_in("喂", 0.15, 0.15))


if __name__ == "__main__":
    unittest.main()
