"""SenseVoice ASR via sherpa-onnx CLI (matches voice/scripts/asr.sh)."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from asr.audio_util import float32_to_int16_bytes, write_wav_int16

LOG = logging.getLogger(__name__)
VOICE_SCRIPTS = Path("/userdata/voice/scripts")


@dataclass
class SenseVoiceConfig:
    model_dir: str = "/userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
    sherpa_bin: str = "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline"
    sherpa_lib: str = "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib"
    language: str = "zh"
    num_threads: int = 2


def _parse_sherpa_json_output(raw: str) -> str:
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = (obj.get("text") or "").strip()
        if text:
            return text
    return ""


def boost_wav_inplace(path: Path) -> None:
    script = VOICE_SCRIPTS / "prep_asr_wav.py"
    if not script.is_file():
        return
    env = os.environ.copy()
    subprocess.run(
        ["python3", str(script), str(path)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


class SenseVoiceAsr:
    def __init__(self, cfg: SenseVoiceConfig | None = None) -> None:
        cfg = cfg or SenseVoiceConfig()
        self.cfg = cfg
        self.model_dir = Path(cfg.model_dir)
        self.tokens = self.model_dir / "tokens.txt"
        self.model = self.model_dir / "model.int8.onnx"
        if not self.model.is_file():
            raise FileNotFoundError(self.model)

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        lib = self.cfg.sherpa_lib
        env["LD_LIBRARY_PATH"] = lib + (f":{env['LD_LIBRARY_PATH']}" if env.get("LD_LIBRARY_PATH") else "")
        return env

    def recognize_file(self, wav_path: str | Path) -> str:
        wav_path = Path(wav_path)
        cmd = [
            self.cfg.sherpa_bin,
            f"--tokens={self.tokens}",
            f"--sense-voice-model={self.model}",
            f"--sense-voice-language={self.cfg.language}",
            f"--num-threads={self.cfg.num_threads}",
            str(wav_path),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self._env(),
        )
        text = _parse_sherpa_json_output(proc.stdout + "\n" + proc.stderr)
        if not text and proc.returncode != 0:
            LOG.warning("[asr] sherpa failed rc=%s stderr=%s", proc.returncode, proc.stderr[-300:])
        return text

    def recognize_samples(
        self,
        samples: list[float],
        sample_rate: int = 16000,
        *,
        boost: bool = False,
        wav_path: Path | None = None,
    ) -> str:
        if len(samples) < sample_rate * 0.3:
            return ""
        target = wav_path or Path(tempfile.gettempdir()) / "agent_asr_chunk.wav"
        pcm = float32_to_int16_bytes(samples)
        write_wav_int16(target, pcm, sample_rate=sample_rate)
        if boost:
            boost_wav_inplace(target)
        return self.recognize_file(target)
