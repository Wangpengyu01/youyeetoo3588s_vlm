"""llm_daemon Unix socket client (shared by orchestrator + scripts)."""
from __future__ import annotations

import json
import socket
import time
import uuid


def llm_chat(
    prompt: str,
    *,
    sock_path: str = "/tmp/r1-llm.sock",
    max_new_tokens: int = 64,
    stream_print: bool = False,
) -> dict:
    payload = {
        "type": "chat",
        "id": str(uuid.uuid4())[:8],
        "prompt": prompt,
        "max_new_tokens": max_new_tokens,
    }
    req_id = payload["id"]
    t0 = time.time()
    ttft: float | None = None
    tokens: list[str] = []

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(120.0)
        s.connect(sock_path)
        s.sendall((json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
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
                if stream_print:
                    print(piece, end="", flush=True)
            elif mtype == "done" and msg.get("id") == req_id:
                usage = msg.get("usage") or {}
                break
            elif mtype == "error":
                raise RuntimeError(msg.get("message", "unknown error"))

    text = "".join(tokens)
    return {
        "id": req_id,
        "text": text,
        "ttft_s": ttft,
        "elapsed_s": time.time() - t0,
        "usage": usage,
    }


def llm_ping(sock_path: str = "/tmp/r1-llm.sock") -> bool:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(2.0)
        s.connect(sock_path)
        s.sendall(b'{"type":"ping"}\n')
        line = s.recv(256).decode("utf-8")
        return "pong" in line
