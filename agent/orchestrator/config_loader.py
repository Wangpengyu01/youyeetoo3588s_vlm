"""Load agent.yaml (stdlib only — supports `key: |` block scalars)."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _parse_scalar(val: str) -> Any:
    val = val.strip().strip('"').strip("'")
    if val.isdigit():
        return int(val)
    try:
        return float(val)
    except ValueError:
        return val


def load_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return {}

    lines = path.read_text(encoding="utf-8").splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while stack and indent < stack[-1][0]:
            stack.pop()

        if line.endswith(":") and not line.startswith("-") and ": " not in line:
            key = line[:-1].strip()
            parent = stack[-1][1]
            if key in parent and isinstance(parent[key], dict):
                node: dict[str, Any] = parent[key]
            else:
                node = {}
                parent[key] = node
            stack.append((indent + 2, node))
            continue

        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        parent = stack[-1][1]

        if val == "|" or val == ">":
            block: list[str] = []
            block_base = indent + 2
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    block.append("")
                    i += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip(" "))
                if nxt_indent < block_base:
                    break
                block.append(nxt.strip())
                i += 1
            text = "\n".join(block).strip("\n")
            if val == ">":
                text = " ".join(block)
            parent[key] = text
            continue

        parent[key] = _parse_scalar(val)
    return root
