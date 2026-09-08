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

    def test_drops_known_leading_junk_before_how_question(self) -> None:
        self.assertEqual(normalize_user_text("那个怎么形成的"), "怎么形成的")


if __name__ == "__main__":
    unittest.main()
