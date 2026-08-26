#!/usr/bin/env python3
"""Minimal JSON-line client for llm_daemon (Phase A board test)."""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import uuid

DEFAULT_SOCK = "/tmp/r1-llm.sock"


def request(sock_path: str, payload: dict, stream: bool = True) -> dict:
    req_id = payload.setdefault("id", str(uuid.uuid4())[:8])
    t0 = time.time()
    ttft: float | None = None
    tokens: list[str] = []

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(120.0)
        s.connect(sock_path)
        s.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        f = s.makefile("rb")
        usage: dict = {}
        while True:
            line = f.readline()
            if not line:
                break
            msg = json.loads(line.decode("utf-8"))
            mtype = msg.get("type")
            if mtype == "token" and msg.get("id") == req_id:
                if ttft is None:
                    ttft = time.time() - t0
                piece = msg.get("text", "")
                tokens.append(piece)
                if stream:
                    print(piece, end="", flush=True)
            elif mtype == "done" and msg.get("id") == req_id:
                usage = msg.get("usage") or {}
                break
            elif mtype == "error":
                raise RuntimeError(msg.get("message", "unknown error"))
            elif mtype == "pong":
                return msg
            elif mtype == "ok":
                return msg
    elapsed = time.time() - t0
    text = "".join(tokens)
    if stream and text:
        print()
    return {
        "id": req_id,
        "text": text,
        "ttft_s": ttft,
        "elapsed_s": elapsed,
        "usage": usage,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="llm_daemon test client")
    p.add_argument("--socket", default=DEFAULT_SOCK)
    p.add_argument("--prompt", help="chat prompt")
    p.add_argument("--ping", action="store_true")
    p.add_argument("--clear", action="store_true")
    p.add_argument("--max-new", type=int, default=64)
    p.add_argument("--no-stream", action="store_true")
    args = p.parse_args()

    if args.ping:
        print(json.dumps(request(args.socket, {"type": "ping"}, stream=False), ensure_ascii=False))
        return
    if args.clear:
        print(json.dumps(request(args.socket, {"type": "clear_history"}, stream=False), ensure_ascii=False))
        return
    if not args.prompt:
        p.error("--prompt required unless --ping or --clear")
    out = request(
        args.socket,
        {
            "type": "chat",
            "prompt": args.prompt,
            "max_new_tokens": args.max_new,
        },
        stream=not args.no_stream,
    )
    if args.no_stream:
        print(out["text"])
    sys.stderr.write(
        f"[client] ttft={out['ttft_s']:.3f}s elapsed={out['elapsed_s']:.3f}s "
        f"chars={len(out['text'])}\n"
    )


if __name__ == "__main__":
    main()
