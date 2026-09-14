from __future__ import annotations

import sys
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from asr.normalize import normalize_user_text  # noqa: E402


class NormalizeUserTextTests(unittest.TestCase):
    def test_keeps_topic_before_how_question(self) -> None:
        self.assertEqual(normalize_user_text("火星是怎么形成的"), "火星是怎么形成的")

    def test_handles_wake_word_prefixes(self) -> None:
        self.assertEqual(normalize_user_text("嘿小揽"), "小揽")
        self.assertEqual(normalize_user_text("嗨小揽"), "小揽")
        self.assertEqual(normalize_user_text("喂小揽"), "小揽")
        self.assertEqual(normalize_user_text("你好小揽"), "你好")
        self.assertEqual(normalize_user_text("嘿小揽今天星期几"), "今天星期几")
        self.assertEqual(normalize_user_text("小揽，桌上有什么"), "桌上有什么")
        self.assertEqual(normalize_user_text("喂小揽帮我看看"), "帮我看")


if __name__ == "__main__":
    unittest.main()
