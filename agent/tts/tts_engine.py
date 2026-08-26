"""VITS-melo TTS via sherpa-onnx (matches voice/scripts/tts.sh)."""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger(__name__)
VOICE_SCRIPTS = Path("/userdata/voice/scripts")


@dataclass
class TtsConfig:
    model_dir: str = "/userdata/voice/vits-melo-tts-zh_en"
    sherpa_bin: str = "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline-tts"
    sherpa_lib: str = "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib"
    num_threads: int = 2
    sid: int = 0
    max_chars: int = 120
    out_wav: str = "/tmp/agent_tts_out.wav"


class TtsEngine:
    def __init__(self, cfg: TtsConfig | None = None) -> None:
        self.cfg = cfg or TtsConfig()
        self.model_dir = Path(self.cfg.model_dir)

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        lib = self.cfg.sherpa_lib
        env["LD_LIBRARY_PATH"] = lib + (f":{env['LD_LIBRARY_PATH']}" if env.get("LD_LIBRARY_PATH") else "")
        return env

    def synthesize(self, text: str, out_path: str | None = None) -> Path:
        text = text.strip()
        if not text:
            raise ValueError("empty TTS text")
        if len(text) > self.cfg.max_chars:
            text = text[: self.cfg.max_chars]
            LOG.info("[tts] truncated to %d chars", self.cfg.max_chars)

        out = Path(out_path or self.cfg.out_wav)
        cmd = [
            self.cfg.sherpa_bin,
            f"--vits-model={self.model_dir / 'model.onnx'}",
            f"--vits-tokens={self.model_dir / 'tokens.txt'}",
            f"--vits-lexicon={self.model_dir / 'lexicon.txt'}",
            f"--vits-dict-dir={self.model_dir / 'dict'}",
            f"--sid={self.cfg.sid}",
            f"--num-threads={self.cfg.num_threads}",
            f"--output-filename={out}",
            text,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=self._env())
        if proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError(f"TTS synth failed: {proc.stderr[-400:]}")
        return out

    def play(self, wav_path: Path) -> None:
        play_script = VOICE_SCRIPTS / "play_wav.sh"
        subprocess.run(["bash", str(play_script), str(wav_path)], check=True)

    def speak(self, text: str) -> None:
        LOG.info("[tts] speak: %s", text[:80])
        wav = self.synthesize(text)
        self.play(wav)
