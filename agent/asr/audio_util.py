"""WAV helpers — stdlib only (no numpy)."""
from __future__ import annotations

import array
import struct
import wave
from pathlib import Path


def int16_bytes_to_float32(raw: bytes) -> list[float]:
    n = len(raw) // 2
    samples = array.array("h")
    samples.frombytes(raw)
    return [s / 32768.0 for s in samples]


def float32_to_int16_bytes(samples: list[float]) -> bytes:
    out = array.array("h")
    for s in samples:
        v = int(max(-32768, min(32767, round(s * 32768.0))))
        out.append(v)
    return out.tobytes()


def write_wav_int16(path: str | Path, pcm: bytes, sample_rate: int = 16000, channels: int = 1) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)


def read_wav_float32(path: str | Path) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise ValueError(f"expected 16-bit PCM, got {wf.getsampwidth()} bytes/sample")
        rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    return int16_bytes_to_float32(raw), rate
