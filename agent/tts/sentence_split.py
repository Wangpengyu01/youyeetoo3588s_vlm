"""Split LLM stream into speakable sentence chunks."""
from __future__ import annotations

import re

_PRIMARY = re.compile(r"([^。！？!?]+[。！？!?])")
_COMMA = re.compile(r"([^，,]{6,40}[，,])")
_CJK = re.compile(r"[\u4e00-\u9fff]")

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


def drain_complete_sentences(buffer: str, *, min_flush_chars: int = 18) -> tuple[list[str], str]:
    """Return completed sentences and leftover buffer."""
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
        m = _COMMA.match(rest)
        if m:
            sent = sanitize_tts_text(m.group(1))
            if sent and _CJK.search(sent):
                out.append(sent)
                rest = rest[m.end() :]
                continue
        if len(rest) >= min_flush_chars:
            chunk = rest[: min_flush_chars + 8]
            if _CJK.search(chunk):
                sent = sanitize_tts_text(chunk)
                if sent:
                    out.append(sent)
                rest = rest[len(chunk) :].lstrip()
                continue
            if len(rest) >= min_flush_chars * 3:
                sent = sanitize_tts_text(rest[:min_flush_chars].strip())
                if sent:
                    out.append(sent)
                rest = rest[min_flush_chars:].lstrip()
                continue
        break
    return out, rest


def flush_remainder(buffer: str) -> list[str]:
    text = sanitize_tts_text(buffer)
    return [text] if text else []
