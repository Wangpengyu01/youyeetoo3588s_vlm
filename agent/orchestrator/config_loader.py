"""Load agent.yaml (stdlib only)."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def load_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return {}
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]
    key_stack: list[str | None] = [None]

    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while stack and indent < stack[-1][0]:
            stack.pop()
            key_stack.pop()

        if line.endswith(":") and not line.startswith("-"):
            key = line[:-1].strip()
            parent = stack[-1][1]
            if key in parent and isinstance(parent[key], dict):
                node: dict[str, Any] = parent[key]
            else:
                node = {}
                parent[key] = node
            stack.append((indent + 2, node))
            key_stack.append(key)
            continue

        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val == "|":
            continue
        parent = stack[-1][1]
        if val.isdigit():
            parent[key] = int(val)
        else:
            try:
                parent[key] = float(val)
            except ValueError:
                parent[key] = val
    return root
