"""llm_daemon Unix socket client (shared by orchestrator + scripts)."""
from __future__ import annotations

import json
import socket
import time
import uuid
from collections.abc import Callable


def _read_chat_stream(
    sock_path: str,
    payload: dict,
    *,
    on_token: Callable[[str], None] | None = None,
    stream_print: bool = False,
) -> dict:
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
                if on_token and piece:
                    on_token(piece)
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


def llm_chat(
    prompt: str,
    *,
    sock_path: str = "/tmp/r1-llm.sock",
    max_new_tokens: int = 64,
    stream_print: bool = False,
    on_token: Callable[[str], None] | None = None,
) -> dict:
    payload = {
        "type": "chat",
        "id": str(uuid.uuid4())[:8],
        "prompt": prompt,
        "max_new_tokens": max_new_tokens,
    }
    return _read_chat_stream(sock_path, payload, on_token=on_token, stream_print=stream_print)


def llm_chat_stream(
    prompt: str,
    on_token: Callable[[str], None],
    *,
    sock_path: str = "/tmp/r1-llm.sock",
    max_new_tokens: int = 64,
) -> dict:
    return llm_chat(
        prompt,
        sock_path=sock_path,
        max_new_tokens=max_new_tokens,
        on_token=on_token,
    )


def llm_ping(sock_path: str = "/tmp/r1-llm.sock") -> bool:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(2.0)
        s.connect(sock_path)
        s.sendall(b'{"type":"ping"}\n')
        line = s.recv(256).decode("utf-8")
        return "pong" in line
