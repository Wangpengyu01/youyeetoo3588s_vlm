"""Prepare and concatenate TTS wav chunks for seamless playback."""
from __future__ import annotations

import struct
import wave
from pathlib import Path


def _read_mono(path: Path) -> tuple[int, list[int]]:
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        nch = w.getnchannels()
        sw = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if sw != 2:
        raise ValueError(f"unsupported sample width: {sw}")
    samples = list(struct.unpack("<%dh" % (len(frames) // 2), frames))
    if nch == 2:
        samples = [(samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples), 2)]
    elif nch != 1:
        raise ValueError(f"unsupported channels: {nch}")
    return rate, samples


def _resample(rate: int, samples: list[int], out_rate: int = 16000) -> list[int]:
    if rate == out_rate:
        return samples
    out_len = max(1, int(len(samples) * out_rate / rate))
    if len(samples) <= 1:
        return samples[:1]
    out: list[int] = []
    for i in range(out_len):
        src = i * (len(samples) - 1) / (out_len - 1)
        j = int(src)
        k = min(j + 1, len(samples) - 1)
        frac = src - j
        out.append(int(samples[j] * (1 - frac) + samples[k] * frac))
    return out


def _trim_edges(samples: list[int], rate: int = 16000, threshold: int = 80, max_ms: int = 50) -> list[int]:
    max_n = int(rate * max_ms / 1000)
    start = 0
    for s in samples[:max_n]:
        if abs(s) >= threshold:
            break
        start += 1
    end = len(samples)
    for s in reversed(samples[-max_n:]):
        if abs(s) >= threshold:
            break
        end -= 1
    if end <= start:
        return samples
    return samples[start:end]


def concat_wavs(
    paths: list[Path],
    out_path: Path,
    *,
    rate: int = 16000,
    pause_ms: int = 90,
) -> Path:
    """Join synth chunks with a short breath pause — one continuous utterance."""
    if not paths:
        raise ValueError("no wav paths")
    if len(paths) == 1:
        return paths[0]
    pause_n = int(rate * pause_ms / 1000)
    merged: list[int] = []
    for path in paths:
        src_rate, samples = _read_mono(path)
        samples = _resample(src_rate, samples, rate)
        samples = _trim_edges(samples, rate=rate)
        if not samples:
            continue
        if merged and pause_n > 0:
            merged.extend([0] * pause_n)
        merged.extend(samples)
    if not merged:
        raise ValueError("empty concatenated audio")
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(merged), *merged))
    return out_path
