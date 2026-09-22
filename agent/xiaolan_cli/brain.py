"""Shared chat + vision logic for shell REPL and orchestrator (WebUI wrapper)."""
from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from llm.client import llm_chat_stream, llm_clear_history, llm_ping
from orchestrator.dialogue_policy import is_vision_query, normalize_spoken_text


class XiaolanBrain:
    def __init__(
        self,
        agent_root: Path | str,
        *,
        socket_path: str = "/tmp/r1-llm.sock",
        max_new_tokens: int = 128,
        backend: str = "llm_daemon",
    ) -> None:
        self.agent_root = Path(agent_root)
        self.scripts = self.agent_root / "scripts"
        self.socket_path = socket_path
        self.max_new_tokens = max_new_tokens
        self.backend = (backend or "llm_daemon").strip()
        self.unified_vlm = self.backend == "vlm_daemon"
        self.default_frame = self.agent_root / "run" / "camera_shot.jpg"

    def ping(self) -> bool:
        return llm_ping(self.socket_path)

    def clear_history(self) -> None:
        llm_clear_history(self.socket_path)

    def wants_vision(self, user_text: str) -> bool:
        clean = normalize_spoken_text(user_text or "")
        return bool(clean) and is_vision_query(clean)

    def chat_stream(
        self,
        prompt: str,
        on_token: Callable[[str], None],
        *,
        max_new_tokens: int | None = None,
    ) -> dict:
        return llm_chat_stream(
            prompt,
            on_token,
            sock_path=self.socket_path,
            max_new_tokens=max_new_tokens or self.max_new_tokens,
        )

    def chat(self, prompt: str, *, max_new_tokens: int | None = None) -> str:
        parts: list[str] = []

        def _collect(p: str) -> None:
            parts.append(p)

        self.chat_stream(prompt, _collect, max_new_tokens=max_new_tokens)
        return "".join(parts)

    def _bash(self, name: str, *args: str, timeout: float = 300.0) -> subprocess.CompletedProcess[str]:
        path = self.scripts / name
        cmd = ["bash", str(path), *args]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(self.agent_root),
        )

    def grab_frame(self, out: Path | None = None, *, rtsp_url: str | None = None) -> Path:
        target = out or self.default_frame
        import os

        env = os.environ.copy()
        if rtsp_url:
            env["RTSP_URL"] = rtsp_url
        self._bash("pause_rtsp_competitors.sh", timeout=30.0)
        path = self.scripts / "grab_camera_frame.sh"
        subprocess.run(
            ["bash", str(path), str(target)],
            capture_output=True,
            text=True,
            timeout=90.0,
            cwd=str(self.agent_root),
            env=env,
        )
        return target

    def see_via_socket(
        self,
        image_path: Path,
        prompt: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """P5b: in-process see on vlm_daemon (no cooperative stop)."""
        import json
        import socket
        import uuid

        req_id = str(uuid.uuid4())[:8]
        payload = {
            "type": "see",
            "id": req_id,
            "image_path": str(image_path),
            "prompt": prompt,
            "max_new_tokens": self.max_new_tokens,
        }
        parts: list[str] = []
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(300.0)
            s.connect(self.socket_path)
            s.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
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
                        if on_token and piece:
                            on_token(piece)
                    elif msg.get("type") == "done" and msg.get("id") == req_id:
                        return "".join(parts).strip() or "画面中未识别到具体物品。"
                    elif msg.get("type") == "error":
                        raise RuntimeError(msg.get("message", "see failed"))
        return "".join(parts).strip()

    def board_vlm(self, image_path: Path, prompt: str) -> str:
        """RK1828 InternVL: P5b socket or legacy cooperative + vlm_see."""
        if self.unified_vlm:
            return self.see_via_socket(image_path, prompt)
        res = self._bash(
            "run_board_vlm.sh",
            str(image_path),
            prompt.strip() or "用一句话描述当前画面。",
            timeout=200.0,
        )
        lines = [ln.strip() for ln in (res.stdout or "").splitlines() if ln.strip()]
        for ln in reversed(lines):
            if ln.startswith("["):
                continue
            return ln
        return "画面中未识别到具体物品。"

    def see_with_grab(self, prompt: str, *, image_path: Path | None = None) -> str:
        """Full see path used by REPL: grab RTSP → board VLM."""
        frame = image_path or self.default_frame
        self.grab_frame(frame)
        if not frame.is_file() or frame.stat().st_size < 1000:
            return ""
        return self.board_vlm(frame, prompt)

    def see_repl_turn(self, user_line: str) -> str:
        if self.unified_vlm:
            self.grab_frame(self.default_frame)
            return self.see_via_socket(self.default_frame, user_line)
        self._bash("cooperative_stop_llm.sh", timeout=30.0)
        try:
            cap = self.see_with_grab(user_line)
        finally:
            self._bash("cooperative_start_llm.sh", timeout=120.0)
        return cap
