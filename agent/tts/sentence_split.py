"""Split LLM stream into speakable sentence chunks."""
from __future__ import annotations

import re

# Primary sentence boundaries (keep delimiter on sentence)
_PRIMARY = re.compile(r"([^。！？!?；;]+[。！？!?；;])")
# Fallback: comma / newline when chunk is long
_SECONDARY = re.compile(r"([^，,\n]+[，,\n])")


def drain_complete_sentences(buffer: str, *, min_flush_chars: int = 18) -> tuple[list[str], str]:
    """Return completed sentences and leftover buffer."""
    out: list[str] = []
    rest = buffer
    while True:
        m = _PRIMARY.match(rest)
        if m:
            sent = m.group(1).strip()
            if sent:
                out.append(sent)
            rest = rest[m.end() :]
            continue
        if len(rest) >= min_flush_chars:
            m2 = _SECONDARY.match(rest)
            if m2:
                sent = m2.group(1).strip()
                if sent:
                    out.append(sent)
                rest = rest[m2.end() :]
                continue
        break
    return out, rest


def flush_remainder(buffer: str) -> list[str]:
    text = buffer.strip()
    return [text] if text else []
