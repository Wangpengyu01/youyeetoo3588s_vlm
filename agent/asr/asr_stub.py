"""Phase B ASR placeholder — saves utterance WAV for Phase C."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from asr.audio_util import float32_to_int16_bytes, write_wav_int16

LOG = logging.getLogger(__name__)
VOICE_SCRIPTS = Path("/userdata/voice/scripts")


class AsrStub:
    def __init__(self, utterance_path: str, min_duration_sec: float = 0.5) -> None:
        self.utterance_path = Path(utterance_path)
        self.min_duration_sec = min_duration_sec

    async def process(self, samples: list[float], sample_rate: int = 16000) -> dict:
        duration = len(samples) / sample_rate
        if duration < self.min_duration_sec:
            LOG.warning("[asr] utterance too short (%.2fs), skip", duration)
            return {"status": "skipped", "reason": "too_short", "duration_sec": duration}

        pcm = float32_to_int16_bytes(samples)
        write_wav_int16(self.utterance_path, pcm, sample_rate=sample_rate)
        LOG.info("[asr] saved utterance %.2fs -> %s", duration, self.utterance_path)

        boosted = self.utterance_path.with_name("last_utterance_boost.wav")
        try:
            subprocess.run(
                ["python3", str(VOICE_SCRIPTS / "prep_asr_wav.py"), str(self.utterance_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if self.utterance_path.exists():
                import shutil

                shutil.copy2(self.utterance_path, boosted)
        except OSError as exc:
            LOG.debug("[asr] prep_asr_wav skipped: %s", exc)

        return {
            "status": "ready",
            "duration_sec": duration,
            "wav": str(self.utterance_path),
            "text": None,
        }
