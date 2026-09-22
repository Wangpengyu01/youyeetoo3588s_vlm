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


def read_prompt_stdin() -> str:
    """Read one line from stdin (binary); adb from Windows often sends GBK/GB18030."""
    raw = sys.stdin.buffer.readline()
    if not raw:
        return ""
    raw = raw.rstrip(b"\r\n")
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def clean_unicode(text: str) -> str:
    """Remove lone surrogates (break json UTF-8 encode / adb mangled input)."""
    if not text:
        return text
    return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")


def safe_print(text: str, *, end: str = "", flush: bool = False) -> None:
    out = clean_unicode(text) + end
    # UTF-8 bytes survive Windows adb console better than locale text mode
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if flush:
        sys.stdout.flush()


def request(sock_path: str, payload: dict, stream: bool = True) -> dict:
    req_id = payload.setdefault("id", str(uuid.uuid4())[:8])
    if "prompt" in payload and isinstance(payload["prompt"], str):
        payload["prompt"] = clean_unicode(payload["prompt"])
    t0 = time.time()
    ttft: float | None = None
    tokens: list[str] = []

    if not __import__("os").path.exists(sock_path):
        raise FileNotFoundError(
            f"{sock_path} not ready — P5b vlm_daemon still loading six-tuple "
            f"(wait 2–5 min; tail -f /userdata/agent/logs/vlm_daemon.log until "
            f"'listening {sock_path}'). Or: bash /userdata/agent/scripts/wait_vlm_sock.sh"
        )

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(120.0)
        s.connect(sock_path)
        line_out = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        s.sendall(line_out.encode("utf-8", errors="replace"))
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
                    safe_print(piece, end="", flush=True)
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
    p.add_argument("--prompt", help="chat prompt (prefer --prompt-stdin from shell CLI)")
    p.add_argument(
        "--prompt-stdin",
        action="store_true",
        help="read one line of prompt from stdin (UTF-8, avoids adb/cmd quoting)",
    )
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
    prompt = args.prompt
    if args.prompt_stdin:
        prompt = read_prompt_stdin()
    if not prompt:
        import os

        prompt = os.environ.get("LLM_CLI_PROMPT", "")
    prompt = clean_unicode(prompt or "")
    if not prompt:
        p.error("--prompt, --prompt-stdin, or LLM_CLI_PROMPT required unless --ping or --clear")
    out = request(
        args.socket,
        {
            "type": "chat",
            "prompt": prompt,
            "max_new_tokens": args.max_new,
        },
        stream=not args.no_stream,
    )
    if args.no_stream:
        safe_print(out["text"] + "\n")
    sys.stderr.write(
        f"[client] ttft={out['ttft_s']:.3f}s elapsed={out['elapsed_s']:.3f}s "
        f"chars={len(out['text'])}\n"
    )


if __name__ == "__main__":
    main()
