import re

# 宽泛关键词：用于用户主动咨询政策原文（RAG 检索）
_TRAVEL_KEYWORDS = ("差旅", "出差", "住宿", "酒店", "标准", "报销", "伙食", "交通")
_ASK_IN_REPLY = re.compile(r"请(?:提供|补充|确认|填写|选择|告知|说明|输入|核对)|请问|需要您|请您|麻烦|烦请|请告知")

# 仅以下三类业务场景展示「差旅建议与规定提醒」
_TRAVEL_APPLY = re.compile(r"出差|差旅(?:申请)?|申请.?出差|安排.?行程|办理.?差旅")
_HOTEL_BOOK = re.compile(r"订(?:酒店|房)|酒店|订房|入住|预订.*酒店|酒店.*预(?:订|约)|住宿(?:标准|费用|预订)")
_TICKET_BOOK = re.compile(r"订票|订(?:机票|车票|高铁|火车|动车|航班)|机票|航班|车票|高铁票|火车票|动车票|铁路(?:票)?|车.?票")

# 非差旅办事流程的确认/交互 metadata（这些场景禁止展示差旅提醒）
NON_TRAVEL_WORKFLOW_META_KEYS = (
    "workpackage_confirm",
    "workpackage_plan_confirm",
    "meeting_plan_confirm",
    "leave_plan_confirm",
    "info_collect_plan_confirm",
    "room_selection",
)

_TRAVEL_WORKFLOW_META_KEYS = (
    "travel_plan_confirm",
    "booking_selection",
)

_CITY_HINTS = (
    "内蒙古", "鄂尔多斯", "呼和浩特", "海拉尔", "北京", "上海", "广州", "深圳",
    "一线", "二线", "三线", "其他城市",
)


def latest_user_line(session_text: str) -> str:
    lines = [line.strip() for line in (session_text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def workflow_probe_text(session_text: str) -> str:
    """判断当前办事意图时：短句/修订语用整段会话，否则看最新一句。"""
    from src.agent.session_context import is_plan_revision_text

    latest = latest_user_line(session_text)
    if not latest:
        return session_text
    if is_plan_revision_text(latest) or len(latest) < 8:
        return session_text
    return latest


def is_non_travel_workflow_intent(text: str) -> bool:
    """会议、工时、请假、信息收集、邮件等非差旅办事意图。"""
    if not (text or "").strip():
        return False
    from src.agent.email_etiquette import is_email_context
    from src.agent.info_collect_workflow import is_info_collect_workflow_intent
    from src.agent.leave_workflow import is_leave_workflow_intent
    from src.agent.meeting_workflow import is_meeting_workflow_intent
    from src.agent.workpackage_workflow import is_workpackage_workflow_intent

    return (
        is_meeting_workflow_intent(text)
        or is_leave_workflow_intent(text)
        or is_workpackage_workflow_intent(text)
        or is_info_collect_workflow_intent(text)
        or is_email_context(text)
    )


def is_travel_workflow_metadata(metadata: dict | None) -> bool:
    if not metadata:
        return False
    return any(metadata.get(key) for key in _TRAVEL_WORKFLOW_META_KEYS)


def is_non_travel_workflow_metadata(metadata: dict | None) -> bool:
    if not metadata:
        return False
    return any(metadata.get(key) for key in NON_TRAVEL_WORKFLOW_META_KEYS)


def is_travel_reminder_eligible(text: str) -> bool:
    """仅差旅申请、酒店预定、车票购买场景展示差旅规定提醒。"""
    if not (text or "").strip():
        return False
    if _TRAVEL_APPLY.search(text):
        return True
    if _HOTEL_BOOK.search(text):
        return True
    if _TICKET_BOOK.search(text):
        return True
    return False


async def should_skip_travel_reminders(
    message_repo,
    session_id: str,
    session_text: str,
    metadata: dict | None,
) -> bool:
    """非差旅办事（含确认卡片）及纯非差旅意图时，不展示差旅建议/规定提醒。"""
    from src.agent.workflow_confirm import get_pending_meta

    if is_travel_workflow_metadata(metadata):
        return False
    if is_non_travel_workflow_metadata(metadata):
        return True

    for key in NON_TRAVEL_WORKFLOW_META_KEYS:
        _, pending = await get_pending_meta(message_repo, session_id, key)
        if pending:
            return True

    probe = workflow_probe_text(session_text)
    if is_non_travel_workflow_intent(probe):
        if not is_travel_reminder_eligible(probe):
            return True
        # 同一句里既有非差旅办事又有订票/酒店等，确认卡片仍由 metadata 控制；此处偏向不打扰非差旅
        if is_non_travel_workflow_intent(probe) and is_travel_reminder_eligible(probe):
            return True

    if not is_travel_reminder_eligible(session_text):
        return True
    return False


def is_travel_policy_context(text: str) -> bool:
    return is_travel_reminder_eligible(text) or any(
        keyword in text for keyword in _TRAVEL_KEYWORDS
    )


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
