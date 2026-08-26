"""Offline TTS — persistent sherpa C API (Matcha/VITS) with CLI fallback."""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

LOG = logging.getLogger(__name__)
VOICE_SCRIPTS = Path("/userdata/voice/scripts")


@dataclass
class TtsConfig:
    backend: str = "matcha"
    model_dir: str = "/userdata/voice/matcha-icefall-zh-baker"
    vocoder: str = "/userdata/voice/vocos-22khz-univ.onnx"
    rule_fsts: list[str] = field(default_factory=list)
    sherpa_bin: str = "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline-tts"
    sherpa_lib: str = "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib"
    num_threads: int = 2
    sid: int = 0
    speed: float = 1.0
    max_chars: int = 80
    out_wav: str = "/tmp/agent_tts_out.wav"


class TtsEngine:
    def __init__(self, cfg: TtsConfig | None = None) -> None:
        self.cfg = cfg or TtsConfig()
        self.model_dir = Path(self.cfg.model_dir)
        self._native: object | None = None
        try:
            from tts.sherpa_tts import SherpaOfflineTts, SherpaTtsConfig

            self._native = SherpaOfflineTts(
                SherpaTtsConfig(
                    backend=self.cfg.backend,
                    model_dir=str(self.model_dir),
                    vocoder=self.cfg.vocoder,
                    rule_fsts=list(self.cfg.rule_fsts),
                    sherpa_lib=self.cfg.sherpa_lib,
                    num_threads=self.cfg.num_threads,
                    sid=self.cfg.sid,
                    speed=self.cfg.speed,
                )
            )
            LOG.info("[tts] loaded %s model (persistent C API)", self.cfg.backend)
        except Exception as exc:
            LOG.warning("[tts] persistent engine unavailable (%s), using CLI", exc)

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        lib = self.cfg.sherpa_lib
        env["LD_LIBRARY_PATH"] = lib + (f":{env['LD_LIBRARY_PATH']}" if env.get("LD_LIBRARY_PATH") else "")
        return env

    def _rule_fsts_str(self) -> str:
        return ",".join(self.cfg.rule_fsts)

    def synthesize(self, text: str, out_path: str | None = None) -> Path:
        text = text.strip()
        if not text:
            raise ValueError("empty TTS text")
        if len(text) > self.cfg.max_chars:
            text = text[: self.cfg.max_chars]
            LOG.info("[tts] truncated to %d chars", self.cfg.max_chars)

        out = Path(out_path or self.cfg.out_wav)
        if self._native is not None:
            return self._native.synthesize_to_wav(text, out)  # type: ignore[union-attr]

        cmd: list[str] = [self.cfg.sherpa_bin]
        if self.cfg.backend == "matcha":
            cmd.extend(
                [
                    f"--matcha-acoustic-model={self.model_dir / 'model-steps-3.onnx'}",
                    f"--matcha-vocoder={self.cfg.vocoder}",
                    f"--matcha-lexicon={self.model_dir / 'lexicon.txt'}",
                    f"--matcha-tokens={self.model_dir / 'tokens.txt'}",
                    f"--matcha-dict-dir={self.model_dir / 'dict'}",
                    f"--matcha-length-scale={1.0 / max(self.cfg.speed, 0.1)}",
                ]
            )
            if self.cfg.rule_fsts:
                cmd.append(f"--tts-rule-fsts={self._rule_fsts_str()}")
        else:
            cmd.extend(
                [
                    f"--vits-model={self.model_dir / 'model.onnx'}",
                    f"--vits-tokens={self.model_dir / 'tokens.txt'}",
                    f"--vits-lexicon={self.model_dir / 'lexicon.txt'}",
                    f"--vits-dict-dir={self.model_dir / 'dict'}",
                    f"--vits-length-scale={1.0 / max(self.cfg.speed, 0.1)}",
                ]
            )
        cmd.extend(
            [
                f"--sid={self.cfg.sid}",
                f"--num-threads={self.cfg.num_threads}",
                f"--output-filename={out}",
                text,
            ]
        )
        proc = subprocess.run(cmd, capture_output=True, text=True, env=self._env())
        if proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError(f"TTS synth failed: {proc.stderr[-400:]}")
        return out

    def play(self, wav_path: Path, *, fast: bool = False) -> None:
        play_script = VOICE_SCRIPTS / "play_wav.sh"
        env = os.environ.copy()
        if fast:
            env["PLAYBACK_WARMUP_SEC"] = "0"
            env["VOICE_RESTORE_MIC"] = "0"
        subprocess.run(["bash", str(play_script), str(wav_path)], check=True, env=env)

    def speak(self, text: str) -> None:
        LOG.info("[tts] speak: %s", text[:80])
        wav = self.synthesize(text)
        self.play(wav, fast=False)
