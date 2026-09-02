import re

DEFAULT_TITLE = "新对话"
_MAX_LEN = 24

_TOPIC_KEYWORDS: tuple[tuple[str, str], ...] = (
    (r"出差|差旅|机票|酒店|订票", "差旅"),
    (r"会议|会议室|预订", "会议"),
    (r"工包|工时", "工包"),
    (r"邮件|写信", "邮件"),
    (r"报销|政策|标准|规定", "政策"),
)


def clean_session_title(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"^[\s\"'「」《》【】]+|[\s\"'「」《》【】]+$", "", text)
    text = re.sub(r"^\*+|\*+$", "", text)
    text = text.replace("\n", " ").strip()
    if not text or text == DEFAULT_TITLE:
        return ""
    return text[:_MAX_LEN]


_STOP_IN_PROJECT = ("去", "到", "在", "跟", "和", "与", "下周", "明天", "今天")


def _extract_project_name(text: str) -> str | None:
    best: str | None = None
    best_prefix_len = 999
    for m in re.finditer("项目", text):
        idx = m.start()
        for size in range(2, 5):
            start = idx - size
            if start < 0:
                continue
            prefix = text[start:idx]
            if any(token in prefix for token in _STOP_IN_PROJECT):
                continue
            if not re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9·]+", prefix):
                continue
            if len(prefix) < best_prefix_len:
                best_prefix_len = len(prefix)
                best = f"{prefix}项目"
    return best


def fallback_session_title(user_messages: list[str]) -> str:
    """LLM 不可用时的规则兜底标题。"""
    if not user_messages:
        return DEFAULT_TITLE
    text = " ".join(user_messages)
    project_match = _extract_project_name(text)
    topics: list[str] = []
    for pattern, label in _TOPIC_KEYWORDS:
        if re.search(pattern, text) and label not in topics:
            topics.append(label)
    if project_match:
        if topics:
            return clean_session_title(f"{project_match}{'及'.join(topics)}") or project_match
        return clean_session_title(f"{project_match}相关") or project_match
    if topics:
        return clean_session_title("及".join(topics))
    first = user_messages[0].strip()
    return clean_session_title(first[:_MAX_LEN]) or DEFAULT_TITLE
