#!/usr/bin/env python3
"""Create a 384x384 JPEG for Qwen3-VL smoke test."""
import struct
import zlib

W, H = 384, 384


def png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def write_png(path: str) -> None:
    rows = []
    for y in range(H):
        row = b"\x00"
        for x in range(W):
            row += bytes((40 + (x // 16) * 3, 120 + (y // 16) * 2, 200))
        rows.append(row)
    raw = b"".join(rows)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    out = "/userdata/models/Qwen3-VL-4B/demo.png"
    write_png(out)
    print(f"Wrote {out} ({W}x{H})")
