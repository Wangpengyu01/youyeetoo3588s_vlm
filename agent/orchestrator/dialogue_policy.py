"""Pure intent and barge-in rules for the voice conversation loop."""
from __future__ import annotations

import re

_SPOKEN_CHARS = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]")

_STOP_COMMANDS = frozenset(
    {
        "停",
        "暂停",
        "停止",
        "别说了",
        "不要说了",
        "闭嘴",
        "算了",
        "打住",
        "停下",
        "别讲",
        "别讲了",
        "不要讲",
        "不要讲了",
        "闭上嘴",
        "别出声",
        "安静",
        "停一下",
        "等等",
        "等一下",
        "你停",
        "你先停",
        "你先停一下",
    }
)

_RESUME_COMMANDS = frozenset(
    {
        "继续",
        "接着说",
        "然后呢",
        "往下说",
        "接着讲",
        "继续讲",
        "继续说",
        "还有呢",
        "你接着说",
        "你继续",
        "接力",
        "你说",
        "你说吧",
        "说吧",
        "你讲",
        "讲吧",
        "说",
        "讲",
        "说下去",
        "接下去说",
        "接力说",
        "继续接力",
        "往下讲",
        "接下来说",
        "请继续",
        "你接着说吧",
    }
)


def normalize_spoken_text(text: str) -> str:
    """Keep only characters that can represent a short spoken command."""
    return _SPOKEN_CHARS.sub("", text or "")


def is_stop_command(text: str) -> bool:
    """Return true only for a complete stop command, never for a substring."""
    return normalize_spoken_text(text) in _STOP_COMMANDS


def is_resume_command(text: str) -> bool:
    """Return true only for a complete continuation command."""
    return normalize_spoken_text(text) in _RESUME_COMMANDS


def can_barge_in(partial_text: str, speech_sec: float, min_speech_sec: float) -> bool:
    """Accept the first distinct recognized syllable after a short voice gate."""
    return bool(normalize_spoken_text(partial_text)) and speech_sec >= min_speech_sec


_VISION_INTENT = re.compile(
    r"("
    r"看[看下一]|"
    r"帮我看|"
    r"你?能?看[到见懂]|"
    r"这[是个]?[什么啥]|"
    r"我拿[的着]|"
    r"拍[个张]?照|"
    r"摄像头|"
    r"镜头|"
    r"画面|"
    r"面前|"
    r"桌[子上面].*(?:放|摆|有|看|什么|啥)|"
    r"看.*(?:桌|面前|镜头|这|画面|放|摆)"
    r")"
)


def is_vision_query(text: str) -> bool:
    """Return true if user speech indicates a visual/multimodal inspection question."""
    clean = re.sub(r"[^\u4e00-\u9fa50-9a-zA-Z]", "", text or "")
    if not clean:
        return False
    return bool(_VISION_INTENT.search(clean))

