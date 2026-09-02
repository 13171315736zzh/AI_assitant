"""任务分类与列表展示辅助。"""

from __future__ import annotations

_CATEGORY_LABELS = {
    "travel": "差旅办事",
    "meeting": "会议预约",
    "workpackage": "工时填报",
    "email": "邮件撰写",
    "other": "综合办事",
}

_TOOL_TAGS: dict[str, str] = {
    "travel_apply": "差旅申请",
    "flight_book": "机票预订",
    "hotel_book": "酒店预订",
    "email_notify": "邮件通知",
    "meeting_book": "会议预约",
    "room_book": "会议室",
    "workpackage_fill": "工时填报",
}


def infer_category(steps: list[dict]) -> str:
    tools = {s.get("tool") for s in steps if s.get("tool")}
    if "workpackage_fill" in tools:
        return "workpackage"
    if "meeting_book" in tools or "room_book" in tools:
        return "meeting"
    if "travel_apply" in tools or "flight_book" in tools or "hotel_book" in tools:
        return "travel"
    if "email_notify" in tools:
        return "email"
    return "other"


def infer_tags(steps: list[dict]) -> list[str]:
    tags: list[str] = []
    for step in steps:
        tool = step.get("tool")
        if tool in ("user_confirm",):
            continue
        label = _TOOL_TAGS.get(tool) or step.get("action")
        if label and label not in tags:
            tags.append(label)
    return tags


def count_completed_steps(steps: list[dict]) -> int:
    return sum(1 for s in steps if s.get("status") == "completed")


def effective_status(raw_status: str, steps: list[dict]) -> str:
    if raw_status == "cancelled":
        return "cancelled"
    if raw_status == "completed":
        return "completed"
    if raw_status == "failed":
        return "failed"
    if steps and all(s.get("status") == "completed" for s in steps):
        return "completed"
    if raw_status in ("running", "pending"):
        return "running"
    return raw_status or "running"


def category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, "综合办事")


def build_task_summary(record) -> dict:
    steps = list(record.steps_json or [])
    total = record.total_steps or len(steps) or 0
    completed = count_completed_steps(steps)
    category = infer_category(steps)
    status = effective_status(record.status, steps)
    progress = int(completed / total * 100) if total else 0

    return {
        "id": record.id,
        "session_id": record.session_id,
        "goal": record.goal,
        "status": status,
        "raw_status": record.status,
        "category": category,
        "category_label": category_label(category),
        "tags": infer_tags(steps),
        "completed_steps": completed,
        "total_steps": total,
        "progress_percent": progress,
        "current_step": record.current_step,
        "replan_count": record.replan_count,
        "created_at": record.created_at.isoformat() if record.created_at else "",
    }
