"""Split LLM stream into speakable sentence chunks."""
from __future__ import annotations

import re

_PRIMARY = re.compile(r"([^。！？!?]+[。！？!?])")

# Strip markdown / list markers that sound bad in TTS
_MD_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_MD_LIST = re.compile(r"^\s*\d+\.\s*", re.MULTILINE)
_MD_HEAD = re.compile(r"^#+\s*", re.MULTILINE)
_ASCII = re.compile(r"[A-Za-z]+")
_WS = re.compile(r"\s+")


def sanitize_tts_text(text: str) -> str:
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_LIST.sub("", text)
    text = _MD_HEAD.sub("", text)
    text = text.replace("*", "").replace("`", "").replace("#", "")
    text = _ASCII.sub("", text)
    text = _WS.sub(" ", text).strip()
    return text


def drain_complete_sentences(buffer: str, *, min_flush_chars: int = 999) -> tuple[list[str], str]:
    """Return completed sentences (。！？ only) and leftover buffer."""
    out: list[str] = []
    rest = buffer
    while True:
        m = _PRIMARY.match(rest)
        if m:
            sent = sanitize_tts_text(m.group(1))
            if sent:
                out.append(sent)
            rest = rest[m.end() :]
            continue
        if len(rest) >= min_flush_chars:
            sent = sanitize_tts_text(rest.strip())
            if sent:
                out.append(sent)
            rest = ""
            break
        break
    return out, rest


def flush_remainder(buffer: str) -> list[str]:
    text = sanitize_tts_text(buffer)
    return [text] if text else []
