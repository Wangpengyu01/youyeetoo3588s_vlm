from __future__ import annotations

import sys
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from orchestrator.config_loader import load_yaml  # noqa: E402


class AgentConfigTests(unittest.TestCase):
    def test_default_mode_mutes_capture_during_tts_without_aec(self) -> None:
        cfg = load_yaml(AGENT_ROOT / "config" / "agent.yaml")
        self.assertEqual(cfg["vad"]["mute_mic_during_tts"], "true")


if __name__ == "__main__":
    unittest.main()
