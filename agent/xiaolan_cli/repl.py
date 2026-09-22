"""Interactive CLI on board TTY (UTF-8 / GB18030 safe). WebUI uses the same brain via orchestrator."""
from __future__ import annotations

import sys
from pathlib import Path


def _read_line() -> str:
    sys.stdout.write("小揽> ")
    sys.stdout.flush()
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


def main(agent_root: Path | None = None) -> int:
    root = Path(agent_root or "/userdata/agent")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from xiaolan_cli.brain import XiaolanBrain

    brain = XiaolanBrain(root)
    print("小揽 CLI（与 WebUI 共用核心）")
    print("  文字直接输入；看图：请查看当前画面 / 桌面上有什么")
    print("  /quit /clear /ping")
    print("")

    while True:
        line = _read_line().strip()
        if not line:
            continue
        if line in ("/quit", "/exit", "quit", "exit"):
            break
        if line == "/clear":
            brain.clear_history()
            print("[ok] history cleared")
            continue
        if line == "/ping":
            print("pong" if brain.ping() else "no llm_daemon")
            continue

        if brain.wants_vision(line):
            print("[cli] 抓取并分析画面…", file=sys.stderr)
            cap = brain.see_repl_turn(line)
            if cap:
                sys.stdout.buffer.write((cap + "\n").encode("utf-8", errors="replace"))
                sys.stdout.flush()
            else:
                print("[cli] 看图失败", file=sys.stderr)
            continue

        def on_tok(p: str) -> None:
            sys.stdout.buffer.write(p.encode("utf-8", errors="replace"))
            sys.stdout.flush()

        try:
            brain.chat_stream(line, on_tok)
            sys.stdout.write("\n")
            sys.stdout.flush()
        except Exception as exc:
            print(f"[cli] chat error: {exc}", file=sys.stderr)

    print("再见。")
    return 0
