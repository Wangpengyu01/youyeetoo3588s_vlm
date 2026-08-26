#!/usr/bin/env python3
"""Ask InternVL LLM on RM1828 with a dynamic text prompt."""
import re
import os
import shutil
import subprocess
import sys
from pathlib import Path

SESSION_SRC = Path("/usr/bin/rknn3_session_test")
SESSION_PATCH = Path("/tmp/llm_ask_patched")
PROMPT_OFFSET_CN = 412824
PROMPT_OFFSET_EN = 412872
PROMPT_MAX_CN = 48
PROMPT_MAX_EN = 46

LLM_DIR = Path("/userdata/models/InternVL3_5-4B")


def patch_prompt(data: bytearray, offset: int, max_len: int, text: str) -> None:
    raw = text.encode("utf-8")
    if len(raw) >= max_len:
        raw = raw[: max_len - 1]
    end = offset
    while end < offset + max_len:
        data[end] = 0
        end += 1
    data[offset : offset + len(raw)] = raw


def build_patched_binary() -> None:
    data = bytearray(SESSION_SRC.read_bytes())
    patch_prompt(data, PROMPT_OFFSET_CN, PROMPT_MAX_CN, "。")
    patch_prompt(data, PROMPT_OFFSET_EN, PROMPT_MAX_EN, ".")
    SESSION_PATCH.write_bytes(data)
    SESSION_PATCH.chmod(0o755)


def run_llm(user_prompt: str, max_new: int = 128) -> str:
    data = bytearray(SESSION_SRC.read_bytes())
    patch_prompt(data, PROMPT_OFFSET_CN, PROMPT_MAX_CN, user_prompt)
    patch_prompt(data, PROMPT_OFFSET_EN, PROMPT_MAX_EN, ".")
    SESSION_PATCH.write_bytes(data)
    SESSION_PATCH.chmod(0o755)

    cmd = [
        str(SESSION_PATCH),
        str(LLM_DIR / "llm_InternVL3_5-4B.rknn"),
        str(LLM_DIR / "llm_InternVL3_5-4B.weight"),
        str(LLM_DIR / "InternVL3_5-4B.tokenizer.gguf"),
        str(LLM_DIR / "InternVL3_5-4B.embed.bin"),
        "1024",
        str(max_new),
        "0xff",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    if proc.returncode != 0:
        sys.stderr.write(output)
        raise SystemExit(proc.returncode)

    blocks = re.findall(
        r"-{20,}Output-{20,}\s*\n(.*?)(?:\n-{10,}|\n\*{3,}|\Z)",
        output,
        flags=re.S,
    )
    if not blocks:
        raise SystemExit("LLM output not found")
    reply = blocks[0].strip()
    reply = reply.split("\n\n")[0].strip()
    return reply


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: llm_ask.py \"your question\"", file=sys.stderr)
        raise SystemExit(2)
    prompt = " ".join(sys.argv[1:]).strip()
    if not prompt:
        raise SystemExit("empty prompt")
    print(run_llm(prompt, max_new=int(os.environ.get("LLM_MAX_NEW", "64"))), end="")


if __name__ == "__main__":
    main()
