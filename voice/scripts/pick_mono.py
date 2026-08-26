#!/usr/bin/env python3
"""Pick the louder channel from stereo wav, write mono."""
import struct
import sys
import wave


def main():
    src, dst = sys.argv[1], sys.argv[2]
    with wave.open(src, "rb") as w:
        nch = w.getnchannels()
        rate = w.getframerate()
        sw = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if sw != 2:
        raise SystemExit("need S16")
    samples = struct.unpack("<%dh" % (len(frames) // 2), frames)
    if nch == 1:
        mono = list(samples)
    elif nch == 2:
        left = [samples[i] for i in range(0, len(samples), 2)]
        right = [samples[i] for i in range(1, len(samples), 2)]
        pl = max(abs(x) for x in left) if left else 0
        pr = max(abs(x) for x in right) if right else 0
        mono = left if pl >= pr else right
        print(f"pick={'L' if pl >= pr else 'R'} peakL={pl} peakR={pr}", file=sys.stderr)
    else:
        raise SystemExit(f"bad channels {nch}")
    with wave.open(dst, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(mono), *mono))


if __name__ == "__main__":
    main()
