"""Light cleanup of streaming ASR text before LLM."""
from __future__ import annotations

import re

_DUP_CHAR = re.compile(r"(.)\1{1,}")
_NAME_FIX = re.compile(r"小懒")
_GREETING_NAME = re.compile(r"^(?:你好)?小揽[，,、\s]*", re.IGNORECASE)


def normalize_user_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text
    text = _DUP_CHAR.sub(r"\1", text)
    text = _NAME_FIX.sub("小揽", text)
    text = _GREETING_NAME.sub("", text)
    text = re.sub(r"\s+", "", text)
    return text.strip()
