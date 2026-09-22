#!/usr/bin/env python3
"""P5b: see request to vlm_daemon (streaming tokens)."""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import uuid

DEFAULT_SOCK = "/tmp/r1-vlm.sock"
DEFAULT_PROMPT = "用一句话描述当前画面。"


def clean_unicode(text: str) -> str:
    if not text:
        return text
    return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")


def read_prompt_stdin() -> str:
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


def see(sock_path: str, image_path: str, prompt: str, *, max_new: int = 128, stream: bool = True) -> str:
    if not os.path.exists(sock_path):
        raise FileNotFoundError(
            f"{sock_path} missing — wait for P5b load: "
            "bash /userdata/agent/scripts/wait_vlm_sock.sh"
        )

    prompt = clean_unicode(prompt)
    req_id = str(uuid.uuid4())[:8]
    payload = {
        "type": "see",
        "id": req_id,
        "image_path": image_path,
        "prompt": prompt,
        "max_new_tokens": max_new,
    }
    line_out = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    parts: list[str] = []
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(300.0)
        s.connect(sock_path)
        s.sendall(line_out.encode("utf-8", errors="replace"))
        buf = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                msg = json.loads(line.decode("utf-8", errors="replace"))
                if msg.get("type") == "token" and msg.get("id") == req_id:
                    piece = msg.get("text", "")
                    parts.append(piece)
                    if stream:
                        sys.stdout.buffer.write(piece.encode("utf-8", errors="replace"))
                        sys.stdout.flush()
                elif msg.get("type") == "done" and msg.get("id") == req_id:
                    if stream and parts:
                        sys.stdout.buffer.write(b"\n")
                        sys.stdout.flush()
                    return "".join(parts)
                elif msg.get("type") == "error":
                    raise RuntimeError(msg.get("message", "see failed"))
    return "".join(parts)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("image", help="JPEG path on board")
    p.add_argument("prompt", nargs="?", default=None, help="vision prompt (prefer --prompt-stdin on board TTY)")
    p.add_argument("--prompt-stdin", action="store_true", help="read prompt line from stdin (UTF-8 / GBK)")
    p.add_argument("--socket", default=DEFAULT_SOCK)
    p.add_argument("--max-new", type=int, default=128)
    p.add_argument("--no-stream", action="store_true")
    args = p.parse_args()

    if args.prompt_stdin:
        prompt = read_prompt_stdin()
    elif args.prompt:
        prompt = args.prompt
    else:
        prompt = os.environ.get("VLM_SEE_PROMPT", DEFAULT_PROMPT)
    prompt = clean_unicode(prompt) or DEFAULT_PROMPT

    text = see(args.socket, args.image, prompt, max_new=args.max_new, stream=not args.no_stream)
    if args.no_stream:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


if __name__ == "__main__":
    main()
