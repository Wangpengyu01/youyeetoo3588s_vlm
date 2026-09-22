from __future__ import annotations

import sys
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from orchestrator.config_loader import load_yaml  # noqa: E402


class AgentConfigTests(unittest.TestCase):
    def test_default_mode_mutes_mic_during_tts_to_prevent_feedback(self) -> None:
        cfg = load_yaml(AGENT_ROOT / "config" / "agent.yaml")
        self.assertIn(str(cfg["vad"]["mute_mic_during_tts"]).lower(), ("true", "1"))

    def test_default_mode_omits_unreliable_llm_history(self) -> None:
        cfg = load_yaml(AGENT_ROOT / "config" / "agent.yaml")
        self.assertEqual(cfg["history_max_turns"], 0)


if __name__ == "__main__":
    unittest.main()
