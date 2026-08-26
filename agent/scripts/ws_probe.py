#!/usr/bin/env python3
"""Minimal WebSocket client probe (stdlib) for agent_api testing."""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import struct
import sys

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def _encode_text(text: str) -> bytes:
    data = text.encode("utf-8")
    n = len(data)
    if n < 126:
        return struct.pack("!BB", 0x81, n) + data
    return struct.pack("!BBH", 0x81, 126, n) + data


async def _read_text(reader: asyncio.StreamReader) -> str | None:
    head = await reader.readexactly(2)
    b1, b2 = head[0], head[1]
    masked = (b2 >> 7) & 1
    length = b2 & 0x7F
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await reader.readexactly(8))[0]
    mask = await reader.readexactly(4) if masked else None
    payload = await reader.readexactly(length)
    if mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    if (b1 & 0x0F) == 0x8:
        return None
    return payload.decode("utf-8", errors="replace")


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.environ.get("AGENT_WS_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("AGENT_WS_PORT", "8765")))
    p.add_argument("--count", type=int, default=3, help="messages to read")
    args = p.parse_args()

    key = base64.b64encode(os.urandom(16)).decode()
    reader, writer = await asyncio.open_connection(args.host, args.port)
    req = (
        f"GET /ws HTTP/1.1\r\n"
        f"Host: {args.host}:{args.port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    writer.write(req.encode())
    await writer.drain()
    status = await reader.readline()
    if b"101" not in status:
        print("handshake failed:", status.decode().strip(), file=sys.stderr)
        return 1
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break

    seen = 0
    got_hello = False
    for _ in range(args.count):
        try:
            msg = await asyncio.wait_for(_read_text(reader), timeout=5.0)
        except asyncio.TimeoutError:
            break
        if msg is None:
            break
        print(msg)
        try:
            obj = json.loads(msg)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "hello":
            got_hello = True
        if obj.get("type") in ("hello", "state", "asr_partial", "llm_token", "tts_sentence", "asr_final"):
            seen += 1
    writer.close()
    return 0 if got_hello and seen >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
