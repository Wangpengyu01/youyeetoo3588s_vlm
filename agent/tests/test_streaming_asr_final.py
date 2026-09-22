from __future__ import annotations

import sys
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from asr.asr_engine import _StreamingParaformerBackend  # noqa: E402


class _FakeRecognizer:
    def __init__(self) -> None:
        self.reset_calls = 0
        self.fed: list[list[float]] = []

    def reset(self) -> None:
        self.reset_calls += 1

    def feed(self, samples: list[float], sample_rate: int) -> str:
        self.fed.append(list(samples))
        return ""

    def finalize(self) -> str:
        return "完整结果"


class StreamingAsrFinalTests(unittest.TestCase):
    def test_final_recognition_replays_the_full_vad_segment_including_preroll(self) -> None:
        recognizer = _FakeRecognizer()
        backend = _StreamingParaformerBackend(recognizer, 16000)
        backend._fed_samples = 2  # Chunks were streamed only after VAD started.
        full_segment = [0.1, 0.2, 0.3, 0.4, 0.5]

        text = backend.finalize(full_segment, 16000)

        self.assertEqual(text, "完整结果")
        self.assertEqual(recognizer.reset_calls, 1)
        self.assertEqual(recognizer.fed, [full_segment])


if __name__ == "__main__":
    unittest.main()
