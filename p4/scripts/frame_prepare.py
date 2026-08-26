#!/usr/bin/env python3
"""Center-crop and resize RTSP JPEG to VLM input size (448x448)."""
import sys
from PIL import Image


def main() -> None:
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} src.jpg dst.jpg size", file=sys.stderr)
        raise SystemExit(2)
    src, dst, size_s = sys.argv[1], sys.argv[2], sys.argv[3]
    size = int(size_s)

    im = Image.open(src).convert("RGB")
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    im = im.crop((left, top, left + side, top + side))
    im = im.resize((size, size), Image.BILINEAR)
    im.save(dst, format="JPEG", quality=92)
    print(f"[frame] {w}x{h} -> {size}x{size} -> {dst}")


if __name__ == "__main__":
    main()
