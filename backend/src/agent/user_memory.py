"""用户长期记忆：注入 Agent 上下文、从对话抽取职位。"""

from __future__ import annotations

import re

# 结构化字段中的占位职级，不算用户已确认
GENERIC_POSITIONS = frozenset({"", "员工", "管理员", "unknown"})

_POSITION_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"主要负责人|公司领导"), "主要负责人"),
    (re.compile(r"其他负责人|部门负责人|副总"), "其他负责人"),
    (re.compile(r"其他人员|普通员工|一般员工|职员"), "其他人员"),
    (re.compile(r"项目经理"), "项目经理"),
)

_ASK_POSITION_HINT = re.compile(r"职级|职位|职务|人员类别|您的职")


def is_position_confirmed(position: str | None) -> bool:
    return bool((position or "").strip()) and (position or "").strip() not in GENERIC_POSITIONS


def extract_position(user_content: str, assistant_context: str | None = None) -> str | None:
    text = (user_content or "").strip()
    if not text:
        return None
    for pattern, label in _POSITION_RULES:
        if pattern.search(text):
            return label
    asked = bool(assistant_context and _ASK_POSITION_HINT.search(assistant_context))
    if asked and len(text) <= 24:
        compact = text.replace("。", "").replace("，", "").strip()
        for _, label in _POSITION_RULES:
            if compact == label or compact.endswith(label):
                return label
        if compact in ("经理", "负责人"):
            return "其他负责人"
    return None


def position_to_travel_staff_level(position: str | None) -> str | None:
    if not position:
        return None
    if position in ("主要负责人", "其他负责人", "其他人员"):
        return position
    if position == "项目经理":
        return "其他人员"
    return None


def build_user_memory_snippets(
    display_name: str,
    structured: dict,
    memory_items: list[dict],
    memory_enabled: bool = True,
) -> str:
    if not memory_enabled:
        return ""
    position = (structured.get("position") or "").strip()
    lines = [
        "\n【当前用户长期记忆（必须优先使用，勿重复追问已知信息）】",
        f"- 姓名：{display_name}（来自登录账号 display_name，写邮件/填单时直接使用，禁止再询问用户姓名）",
    ]
    if is_position_confirmed(position):
        lines.append(f"- 职位/职级：{position}（用户已确认并写入长期记忆，禁止再次询问职级/职位）")
        travel_level = position_to_travel_staff_level(position)
        if travel_level:
            lines.append(f"- 差旅人员类别：{travel_level}（按此职级引用住宿/交通标准）")
    else:
        lines.append(
            "- 职位/职级：尚未确认（仅当本次办事确实需要职级且用户未提供时，可礼貌询问一次；"
            "用户答复后将自动写入长期记忆，此后勿再问）"
        )
    for item in memory_items[:6]:
        key = (item.get("key") or "").strip()
        value = (item.get("value") or "").strip()
        if key and value:
            lines.append(f"- {key}：{value}")
    return "\n".join(lines)
