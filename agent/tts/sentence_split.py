"""Split LLM stream into speakable sentence chunks."""
from __future__ import annotations

import re

_PRIMARY = re.compile(r"([^。！？!?\n]+[。！？!?\n])")
_CJK = re.compile(r"[\u4e00-\u9fff]")

_MD_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_MD_LIST = re.compile(r"^\s*[-*•]\s*", re.MULTILINE)
_MD_NUM_LIST = re.compile(r"^\s*\d+[\.、]\s*", re.MULTILINE)
_MD_HEAD = re.compile(r"^#+\s*", re.MULTILINE)

LETTER_MAP = {
    "A": "诶", "B": "必", "C": "西", "D": "弟", "E": "伊", "F": "艾弗",
    "G": "吉", "H": "艾尺", "I": "爱", "J": "借", "K": "开", "L": "艾勒",
    "M": "艾姆", "N": "恩", "O": "欧", "P": "批", "Q": "丘", "R": "阿尔",
    "S": "艾斯", "T": "踢", "U": "优", "V": "微", "W": "达布溜", "X": "艾克斯",
    "Y": "歪", "Z": "贼",
}

COMMON_EN = [
    (r"\b(hello|hi)\b", "哈喽"),
    (r"\bok(ay)?\b", "好的"),
    (r"\b(bye|goodbye)\b", "再见"),
    (r"\b(yes|yeah)\b", "是的"),
    (r"\bno\b", "不"),
    (r"\bgood\b", "好"),
    (r"\bai\b", "人工智能"),
    (r"\bapp\b", "应用"),
    (r"\bapi\b", "接口"),
    (r"\bintern-?s1\b", "小揽"),
    (r"\bintern\b", "小揽"),
    (r"\br1\b", "阿尔一"),
    (r"\bcpu\b", "处理器"),
    (r"\bgpu\b", "显卡"),
    (r"\bnpu\b", "神经网络处理器"),
    (r"\busb\b", "优盘"),
    (r"\bwifi\b", "无线网"),
]

_DIGIT_MAP = str.maketrans("0123456789", "零一二三四五六七八九")
_MIN_SPOKEN_CHARS = 2


def transliterate_en(text: str) -> str:
    """Map common English words and letters to Chinese phonetics for pure-Chinese TTS."""
    for pattern, rep in COMMON_EN:
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)

    def repl_letter(m: re.Match[str]) -> str:
        ch = m.group(0).upper()
        return LETTER_MAP.get(ch, ch)

    return re.sub(r"[A-Za-z]", repl_letter, text)


def sanitize_tts_text(text: str) -> str:
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_LIST.sub("，", text)
    text = _MD_NUM_LIST.sub("，", text)
    text = _MD_HEAD.sub("", text)
    text = text.replace("*", "").replace("`", "").replace("#", "")
    # LLM 常复读 prompt 里的「小揽：」前缀或标记
    text = re.sub(r"^小揽[：:]\s*", "", text)
    text = re.sub(r"<\|im_end\|>.*", "", text)
    text = re.sub(r"<\|.*?\|>", "", text)
    text = re.sub(r"三[Dd]?打印", "三维打印", text, flags=re.IGNORECASE)
    # 冒号、分号转逗号停顿，换行转句号
    text = re.sub(r"[：:；;]+", "，", text)
    text = re.sub(r"[\r\n]+", "。", text)
    # 数字转汉字
    text = text.translate(_DIGIT_MAP)
    # 英文音译转汉字发音
    text = transliterate_en(text)
    # 过滤无法发音的符号
    text = re.sub(r"[-—–\.．\(\)（）【】\[\]「」\"\"\'\'·=]+", "", text)
    text = re.sub(r"[^\u4e00-\u9fff。！？，]", "", text)
    text = re.sub(r"[，。！？]+([。！？])", r"\1", text)
    text = re.sub(r"^[，。！？]+", "", text)
    text = re.sub(r"[，]{2,}", "，", text)
    return text.strip()


def is_speakable(text: str) -> bool:
    return len(re.findall(r"[\u4e00-\u9fff0-9]", text)) >= _MIN_SPOKEN_CHARS


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


_BAD_REPLY = re.compile(
    r"人工智能|以下是|我可以帮助|助手|没有名字|小AI|有什么需要|帮忙的吗"
    r"|爱因斯坦|广义相对论|自然界|深度学习|Transformer|以下方法|如果您能提供|乐意帮助"
    r"|乐意为你讲述|感兴趣的主题|请告诉我你.*需求|创作一个简短"
)
_CAPABILITY = re.compile(r"做什么|会什么|能干|帮我什么|都会做")
_STORY = re.compile(r"故事|哄我|睡前|讲个笑话|讲个故事|讲讲话|讲个话|笑话")
_NAME = re.compile(r"叫什么|名字|你是谁|哪位")
_RECITE = re.compile(r"背诵|元素周期|周期表|乘法表|九九表")
_STOP = re.compile(r"(停|暂停|别说了|不要说了|闭嘴|算了|打住|停止|停下|别讲了|安静|不要讲|停一下)")
_INTRO_PREFIX = re.compile(r"^(?:我叫小揽|我是小揽)[，,。\s]*")
_NAME_ONLY = re.compile(r"^(?:我叫小揽|我是小揽)[。！？]?$")
_SCIENCE_LECTURE = re.compile(r"引力是|基本力|时空弯曲|训练数据|超参数")
_STORY_FALLBACKS = (
    "好呀，小狐狸在夜里找星星，走累了靠着月亮睡了。风轻轻吹，它梦见彩虹。晚安，好梦。",
    "从前有只小兔子，每天傍晚都在窗台等晚霞。有一天晚霞落在它耳朵上，变成了一朵温暖的花。",
    "夜里，小猫抱着月亮的倒影睡着了，梦里它在一整片星星上跳来跳去。",
)


def _story_fallback(user_text: str) -> str:
    idx = sum(ord(c) for c in user_text) % len(_STORY_FALLBACKS)
    return _STORY_FALLBACKS[idx]


def user_asked_name(user_text: str) -> bool:
    return bool(_NAME.search(user_text))


def clean_llm_reply(user_text: str, reply: str) -> str:
    """Strip spurious self-intro and thinking tags."""
    text = (reply or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?think>", "", text)
    text = re.sub(r"<\|.*?\|>", "", text)
    text = re.sub(r"^小揽[：:]\s*", "", text)
    if not user_asked_name(user_text):
        text = _INTRO_PREFIX.sub("", text).strip()
    if not user_asked_name(user_text) and _NAME_ONLY.match(sanitize_tts_text(text)):
        return ""
    return text.strip()


def is_spurious_name_reply(user_text: str, reply: str) -> bool:
    if user_asked_name(user_text):
        return False
    clean = sanitize_tts_text(clean_llm_reply(user_text, reply))
    if not clean:
        return True
    return len(_CJK.findall(clean)) <= 8 and bool(re.search(r"叫小揽|是小揽", clean))


def is_robotic_reply(text: str) -> bool:
    return False


def is_off_topic_reply(user_text: str, reply: str) -> bool:
    return False


_PRESENCE = re.compile(r"^(你?在[吗嘛]|人呢|你在[哪哪儿]|在不在|小揽)[呀啊吧]?$")


def persona_reply_for(user_text: str) -> str:
    """仅在 LLM 完全无输出或崩溃时的真正兜底。"""
    u = user_text.strip()
    if _STOP.search(u):
        return "好的。"
    if _PRESENCE.search(u):
        return "在呢在呢，我一直都在，请问有什么可以帮您的？"
    return "在呢，请问有什么我可以帮您的吗？"


def canned_reply_for(user_text: str) -> str | None:
    u = user_text.strip()
    if _STOP.search(u):
        return "好的。"
    if _PRESENCE.search(u):
        return "在呢在呢，我是小揽，随时为您服务！"
    return None


def should_skip_llm(user_text: str) -> bool:
    return canned_reply_for(user_text) is not None


def pick_first_sentence(text: str) -> str:
    sents = extract_speak_sentences(text, max_cjk=9999)
    return sents[0] if sents else ""


def extract_speak_sentences(text: str, max_cjk: int = 99999, *, max_chunk_len: int = 24) -> list[str]:
    """Split into natural, conversational speakable chunks with proper comma pauses."""
    if max_cjk <= 0:
        return []
    uncapped = max_cjk >= 9999

    # 1. Split on sentence-ending punctuation or newlines
    raw_parts = re.split(r"([。！？!?\n]+)", text)
    sentences: list[str] = []
    for i in range(0, len(raw_parts) - 1, 2):
        s = raw_parts[i].strip()
        p = raw_parts[i + 1].strip()
        if s:
            sentences.append(s + (p if p in "。！？!?" else "。"))
    if len(raw_parts) % 2 == 1 and raw_parts[-1].strip():
        sentences.append(raw_parts[-1].strip() + "。")

    # 2. Refine each sentence with natural comma chunking
    out: list[str] = []
    used = 0
    for raw_s in sentences:
        s_clean = sanitize_tts_text(raw_s)
        if not is_speakable(s_clean):
            continue

        # If sentence is long and has commas, break at clause boundaries
        chunks_to_add: list[str] = []
        if len(s_clean) > max_chunk_len and "，" in s_clean:
            clauses = s_clean.split("，")
            buf = ""
            for c in clauses:
                c = c.strip("，。！？")
                if not c:
                    continue
                if not buf:
                    buf = c
                elif len(buf) + len(c) + 1 <= max_chunk_len:
                    buf += "，" + c
                else:
                    chunks_to_add.append(buf + "。")
                    buf = c
            if buf:
                chunks_to_add.append(buf + "。")
        else:
            chunks_to_add.append(s_clean if s_clean.endswith(("。", "！", "？")) else s_clean + "。")

        for chunk in chunks_to_add:
            n = count_cjk(chunk)
            if not uncapped and used + n > max_cjk:
                tail = cap_speak_text(chunk, max_cjk - used)
                if tail:
                    out.append(tail)
                return out
            out.append(chunk)
            used += n

    return out


def flush_remainder(buffer: str) -> list[str]:
    text = sanitize_tts_text(buffer)
    return [text] if is_speakable(text) else []


class StreamingSentenceSplitter:
    """Consumes LLM tokens in real-time, emitting speakable clauses/sentences as early as possible."""

    def __init__(self, min_clause_chars: int = 8, max_clause_chars: int = 24):
        self.min_clause_chars = min_clause_chars
        self.max_clause_chars = max_clause_chars
        self._buf = ""
        self._think_active = False
        self._first_chunk_emitted = False

    def feed(self, piece: str) -> list[str]:
        self._buf += piece
        if "<think>" in self._buf:
            self._think_active = True
        if self._think_active:
            if "</think>" in self._buf:
                self._buf = self._buf.split("</think>", 1)[1]
                self._think_active = False
            else:
                return []

        # Strip prefixes and special tokens
        self._buf = re.sub(r"^小揽[：:]\s*", "", self._buf)
        self._buf = re.sub(r"<\|.*?\|>", "", self._buf)

        chunks: list[str] = []
        # Natural Clause Split: require at least 8 characters before comma split to prevent isolated short subjects
        curr_min = 8 if not self._first_chunk_emitted else self.min_clause_chars
        curr_max = 24 if not self._first_chunk_emitted else self.max_clause_chars

        while True:
            # 1. Check for sentence-ending punctuation (。！？!?\n)
            m = re.search(r"[。！？!?\n]+", self._buf)
            if m:
                end_pos = m.end()
                raw_chunk = self._buf[:end_pos].strip()
                self._buf = self._buf[end_pos:]
                clean = sanitize_tts_text(raw_chunk)
                if is_speakable(clean):
                    if not clean.endswith(("。", "！", "？")):
                        clean += "。"
                    chunks.append(clean)
                    self._first_chunk_emitted = True
                    curr_min = self.min_clause_chars
                    curr_max = self.max_clause_chars
                continue

            # 2. Check for clause boundaries (，,；;、) when buffer has enough characters
            m_comma = re.search(r"[，,；;、]+", self._buf)
            if m_comma and m_comma.start() >= curr_min:
                end_pos = m_comma.end()
                raw_chunk = self._buf[:end_pos].strip()
                self._buf = self._buf[end_pos:]
                clean = sanitize_tts_text(raw_chunk)
                if is_speakable(clean):
                    if not clean.endswith(("。", "！", "？", "，")):
                        clean += "，"
                    chunks.append(clean)
                    self._first_chunk_emitted = True
                    curr_min = self.min_clause_chars
                    curr_max = self.max_clause_chars
                continue

            # 3. Buffer length safety cap (forces first chunk at curr_max for instant TTFT speech)
            if len(self._buf) >= curr_max:
                raw_chunk = self._buf[:curr_max].strip()
                self._buf = self._buf[curr_max:]
                clean = sanitize_tts_text(raw_chunk)
                if is_speakable(clean):
                    if not clean.endswith(("。", "！", "？", "，")):
                        clean += "，"
                    chunks.append(clean)
                    self._first_chunk_emitted = True
                    curr_min = self.min_clause_chars
                    curr_max = self.max_clause_chars
                continue

            break

        return chunks

    def finish(self) -> list[str]:
        if not self._buf.strip():
            return []
        raw = self._buf.strip()
        self._buf = ""
        clean = sanitize_tts_text(raw)
        if is_speakable(clean):
            if not clean.endswith(("。", "！", "？")):
                clean += "。"
            return [clean]
        return []

