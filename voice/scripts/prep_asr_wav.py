#!/usr/bin/env python3
"""Boost quiet mic recordings before SenseVoice ASR (in-place)."""
import os
import struct
import sys
import wave


def load(path):
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        nch = w.getnchannels()
        sw = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if sw != 2:
        raise SystemExit(f"unsupported sample width: {sw}")
    samples = list(struct.unpack("<%dh" % (len(frames) // 2), frames))
    if nch == 2:
        samples = [(samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples), 2)]
    return rate, samples


def save(path, rate, samples, nch=1):
    with wave.open(path, "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))


def main():
    path = sys.argv[1]
    min_peak = int(os.environ.get("ASR_BOOST_MIN_PEAK", "2500"))
    target = int(os.environ.get("ASR_TARGET_PEAK", "12000"))
    max_gain = float(os.environ.get("ASR_MAX_GAIN", "12.0"))

    rate, samples = load(path)
    peak = max((abs(s) for s in samples), default=0)
    if peak <= 0 or peak >= min_peak:
        print(f"[ASR] prep peak={peak} gain=1.00 (skip)", file=sys.stderr)
        return

    gain = min(max_gain, target / peak)
    boosted = []
    for s in samples:
        v = int(s * gain)
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        boosted.append(v)

    new_peak = max((abs(s) for s in boosted), default=0)
    save(path, rate, boosted)
    print(
        f"[ASR] prep peak={peak}->{new_peak} gain={gain:.2f} (quiet mic boost)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
