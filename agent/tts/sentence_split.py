"""Split LLM stream into speakable sentence chunks."""
from __future__ import annotations

import re

_PRIMARY = re.compile(r"([^。！？!?]+[。！？!?])")
_CJK = re.compile(r"[\u4e00-\u9fff]")

_MD_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_MD_LIST = re.compile(r"^\s*\d+\.\s*", re.MULTILINE)
_MD_HEAD = re.compile(r"^#+\s*", re.MULTILINE)
_ASCII = re.compile(r"[A-Za-z]+")
_DIGITS = re.compile(r"\d+")
# TTS 只保留汉字和句末标点；冒号/分号/括号等会被念出来且很难听
_NON_SPOKEN = re.compile(r"[^\u4e00-\u9fff。！？，]")
_WS = re.compile(r"\s+")

_MIN_CJK_CHARS = 4


def sanitize_tts_text(text: str) -> str:
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_LIST.sub("", text)
    text = _MD_HEAD.sub("", text)
    text = text.replace("*", "").replace("`", "").replace("#", "")
    text = _ASCII.sub("", text)
    text = _DIGITS.sub("", text)
    text = re.sub(r"[：:；;、·\-—–\.．\(\)（）【】\[\]「」\"\"'\"]+", "", text)
    text = _NON_SPOKEN.sub("", text)
    text = _WS.sub("", text)
    text = re.sub(r"[，]{2,}", "，", text)
    text = re.sub(r"^[，。！？]+", "", text)
    text = re.sub(r"[，]+$", "", text)
    return text.strip()


def is_speakable(text: str) -> bool:
    return len(_CJK.findall(text)) >= _MIN_CJK_CHARS


def count_cjk(text: str) -> int:
    return len(_CJK.findall(text))


def cap_speak_text(text: str, max_cjk: int) -> str:
    """Hard cap on spoken Chinese characters; prefer ending at 。！？."""
    if max_cjk <= 0:
        return ""
    text = sanitize_tts_text(text)
    if not text:
        return ""
    if count_cjk(text) <= max_cjk:
        return text
    buf: list[str] = []
    cjk = 0
    for ch in text:
        buf.append(ch)
        if _CJK.match(ch):
            cjk += 1
        if cjk >= max_cjk:
            break
    chunk = "".join(buf)
    last_end = 0
    for m in _PRIMARY.finditer(chunk):
        last_end = m.end()
    if last_end:
        chunk = chunk[:last_end]
    else:
        chunk = chunk.rstrip("，") + "。"
    chunk = sanitize_tts_text(chunk)
    return chunk if is_speakable(chunk) else ""


def drain_complete_sentences(buffer: str, *, min_flush_chars: int = 22) -> tuple[list[str], str]:
    """Only emit on 。！？ — never flush mid-sentence fragments."""
    out: list[str] = []
    rest = buffer
    while True:
        m = _PRIMARY.match(rest)
        if m:
            sent = sanitize_tts_text(m.group(1))
            if is_speakable(sent):
                out.append(sent)
            rest = rest[m.end() :]
            continue
        break
    return out, rest


_BAD_REPLY = re.compile(r"人工智能|以下是|我可以帮助您|助手，可以")
_CAPABILITY = re.compile(r"做什么|会什么|能干|帮我什么")


def is_robotic_reply(text: str) -> bool:
    return bool(_BAD_REPLY.search(text))


def canned_reply_for(user_text: str) -> str | None:
    if _CAPABILITY.search(user_text):
        return "我能跟你聊天，还能帮你看情况。"
    return None


def pick_first_sentence(text: str) -> str:
    m = _PRIMARY.search(text)
    if m:
        sent = sanitize_tts_text(m.group(1))
        if is_speakable(sent):
            return sent
    sent = sanitize_tts_text(text)
    return sent if is_speakable(sent) else ""


def flush_remainder(buffer: str) -> list[str]:
    text = sanitize_tts_text(buffer)
    return [text] if is_speakable(text) else []
