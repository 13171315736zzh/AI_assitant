import re

# 追问前缀：其后紧跟的即为待用户填写/确认的槽位字段名（不限具体词表）
_ASK_LEAD = (
    r"(?:"
    r"请(?:先|再)?(?:提供|补充|确认|填写|选择|告知|说明|输入|核对)|"
    r"请问|"
    r"(?:还|亦)?(?:需要|需)(?:您|你)?(?:再)?(?:提供|补充|确认|填写|告知)?|"
    r"需要您(?:提供|补充|确认|填写|告知)|"
    r"请您(?:提供|补充|确认|填写|告知)|"
    r"麻烦(?:您|你)?(?:提供|补充|告知)|"
    r"烦请(?:您|你)?(?:提供|补充|告知)|"
    r"请告诉我(?:您|你)?(?:的)?|"
    r"请告知(?:您|你)?(?:的)?"
    r")"
    r"(?:您|你)?(?:的)?"
)

# 是否包含向用户追问/索信息的语义
_ASK_PATTERN = re.compile(
    r"请(?:先|再)?(?:提供|补充|确认|填写|选择|告知|说明|输入|核对)|"
    r"请问|(?:还|亦)?(?:需要|需)|需要您|请您|麻烦|烦请|请告诉我|请告知"
)

# 前缀 + 多个槽位（和、及、与、，、, 分隔）
_ASK_FIELD_LIST = re.compile(
    r"(" + _ASK_LEAD + r")"
    + r"([\u4e00-\u9fffA-Za-z0-9·]{2,12}(?:[和、及与][\u4e00-\u9fffA-Za-z0-9·]{2,12})*)"
    + r"(?=[，。！？；：\n]|$)"
)

# 前缀 + 单个槽位（后面常接「是/为/在…」）
_ASK_FIELD_SINGLE = re.compile(
    r"(" + _ASK_LEAD + r")" + r"([\u4e00-\u9fffA-Za-z0-9·]{2,12}?(?=[是为在及，。！？；：\n]|$))"
)

_LIST_SEP = re.compile(r"[和、及与]")
_FIELD_TOKEN = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9·]{2,12}$")

# 指代语 / 疑问词：不是槽位字段名
_SKIP_PREFIXES = ("以上", "上述", "以下", "如下", "这些", "这个", "那个")
_SKIP_TOKENS = frozenset(
    {
        "以上信息",
        "上述信息",
        "以下信息",
        "这些信息",
        "上述内容",
        "以下内容",
        "如下信息",
        "什么",
        "哪些",
        "多少",
        "如何",
        "是否",
        "能否",
        "一下",
        "具体",
        "详细",
        "正确",
        "准确",
        "完整",
        "是否统一安排食宿",
        "统一安排食宿",
    }
)


def _is_slot_field(token: str) -> bool:
    token = token.strip()
    if not token or not _FIELD_TOKEN.fullmatch(token):
        return False
    if token in _SKIP_TOKENS:
        return False
    if any(token.startswith(prefix) for prefix in _SKIP_PREFIXES):
        return False
    if token.isdigit():
        return False
    if "还是" in token:
        return False
    return True


def _bold_token(token: str) -> str:
    if not _is_slot_field(token):
        return token
    if token.startswith("**") and token.endswith("**"):
        return token
    return f"**{token}**"


def _bold_field_list(body: str) -> str:
    pieces = re.split(r"([和、及与])", body)
    return "".join(
        piece if _LIST_SEP.fullmatch(piece) else _bold_token(piece)
        for piece in pieces
        if piece
    )


def _apply_patterns(text: str) -> str:
    result = text
    for pattern, formatter in (
        (_ASK_FIELD_LIST, lambda m: m.group(1) + _bold_field_list(m.group(2))),
        (
            _ASK_FIELD_SINGLE,
            lambda m: m.group(1) + (_bold_token(m.group(2)) if _is_slot_field(m.group(2)) else m.group(2)),
        ),
    ):
        chunks: list[str] = []
        last = 0
        for match in pattern.finditer(result):
            chunks.append(result[last : match.start()])
            chunks.append(formatter(match))
            last = match.end()
        chunks.append(result[last:])
        result = "".join(chunks)
    return result


def emphasize_slot_labels(text: str) -> str:
    """对本句所有待用户填写/补充/确认的槽位字段名加粗（不限固定词表）。"""
    if not text or not _ASK_PATTERN.search(text):
        return text
    return _apply_patterns(text)
