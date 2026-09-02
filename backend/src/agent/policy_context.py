import re

_TRAVEL_KEYWORDS = ("差旅", "出差", "住宿", "酒店", "标准", "报销", "伙食", "交通")
_ASK_IN_REPLY = re.compile(r"请(?:提供|补充|确认|填写|选择|告知|说明|输入|核对)|请问|需要您|请您|麻烦|烦请|请告知")

_CITY_HINTS = (
    "内蒙古", "鄂尔多斯", "呼和浩特", "海拉尔", "北京", "上海", "广州", "深圳",
    "一线", "二线", "三线", "其他城市",
)


def is_travel_policy_context(text: str) -> bool:
    return any(keyword in text for keyword in _TRAVEL_KEYWORDS)


def should_show_policy_with_question(user_content: str, assistant_content: str) -> bool:
    combined = f"{user_content}\n{assistant_content}"
    if not is_travel_policy_context(combined):
        return False
    if _ASK_IN_REPLY.search(assistant_content):
        return True
    if "标准" in combined and any(word in assistant_content for word in ("确认", "适用", "依据", "按规定")):
        return True
    return False


def build_policy_search_query(user_content: str, assistant_content: str = "") -> str:
    text = f"{user_content} {assistant_content}"
    hints = [part for part in _CITY_HINTS if part in text]
    base = " ".join(hints) if hints else user_content
    if is_travel_policy_context(text) and "住宿" not in base and "标准" not in base:
        base = f"{base} 住宿标准 其他人员"
    return base.strip()


def trim_excerpt(text: str, max_len: int = 320) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip() + "…"


def format_policy_snippets(excerpts: list[dict]) -> str:
    if not excerpts:
        return ""
    lines = [
        "\n\n【可参考的政策条款（向用户确认差旅标准时，须先引用原文中的具体标准数值，再追问）】"
    ]
    for item in excerpts:
        filename = item.get("filename") or "政策文件"
        clause = item.get("clause") or "相关条款"
        excerpt = item.get("excerpt") or ""
        lines.append(f"- 《{filename}》{clause}：{excerpt}")
    return "\n".join(lines)
