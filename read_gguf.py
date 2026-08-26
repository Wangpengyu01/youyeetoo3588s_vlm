#!/usr/bin/env python3
"""Minimal GGUF KV reader for chat_template."""
import struct
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "Qwen3-VL-4B.tokenizer.gguf"

GGUF_MAGIC = 0x46554747
GGUF_VERSION = 3
GGUF_VAL_STR = 8


def read_string(f):
    (n,) = struct.unpack("<Q", f.read(8))
    return f.read(n).decode("utf-8", errors="replace")


def skip_value(f, vtype):
    if vtype in (0, 7):  # UINT8, BOOL
        f.read(1)
    elif vtype in (1, 5):  # INT8, INT16
        f.read(2)
    elif vtype in (2, 3, 6):  # INT16/32, FLOAT32
        f.read(4)
    elif vtype in (4, 10, 11):  # INT64, UINT64
        f.read(8)
    elif vtype == 8:  # STRING
        read_string(f)
    elif vtype == 9:  # ARRAY
        (atype,) = struct.unpack("<I", f.read(4))
        (count,) = struct.unpack("<Q", f.read(8))
        for _ in range(count):
            skip_value(f, atype)
    elif vtype == 12:  # FLOAT64
        f.read(8)
    else:
        raise ValueError(f"unknown type {vtype}")


with open(path, "rb") as f:
    magic, version = struct.unpack("<II", f.read(8))
    assert magic == GGUF_MAGIC
    (nt,) = struct.unpack("<Q", f.read(8))
    (kv,) = struct.unpack("<Q", f.read(8))
    print(f"version={version} tensors={nt} kv={kv}")
    for _ in range(kv):
        key = read_string(f)
        (vtype,) = struct.unpack("<I", f.read(4))
        if vtype == GGUF_VAL_STR:
            val = read_string(f)
            if "chat" in key or "template" in key:
                print(f"\n=== {key} ===\n{val[:2000]}")
        else:
            skip_value(f, vtype)
