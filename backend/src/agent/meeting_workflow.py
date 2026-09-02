"""会议预约流程：槽位收集、会议室冲突与推荐。"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MEETING_INTENT = re.compile(r"会议|会议室|预约|预订|订会议")
_ROOM_PATTERN = re.compile(r"(\d{3})\s*会议室|会议室\s*(\d{3})")


@dataclass
class MeetingPlan:
    subject: str | None = None
    room: str | None = None
    date_hint: str | None = None
    start_hint: str | None = None
    end_hint: str | None = None
    attendees: str | None = None
    raw_goal: str = ""


def is_meeting_workflow_intent(text: str) -> bool:
    return bool(_MEETING_INTENT.search(text)) and bool(_ROOM_PATTERN.search(text))


def _merge_user_text(messages) -> str:
    parts: list[str] = []
    for record in messages:
        if record.role == "user" and record.content.strip():
            parts.append(record.content.strip())
    return "\n".join(parts)


def build_meeting_plan(messages) -> MeetingPlan:
    combined = _merge_user_text(messages)
    plan = MeetingPlan(raw_goal=combined[:200])

    room_match = _ROOM_PATTERN.search(combined)
    if room_match:
        plan.room = room_match.group(1) or room_match.group(2)

    if re.search(r"明天", combined):
        plan.date_hint = "明天"
    elif re.search(r"后天", combined):
        plan.date_hint = "后天"
    elif re.search(r"本周四|星期四|周四", combined):
        plan.date_hint = "本周四"

    if re.search(r"下午", combined):
        plan.start_hint = "下午"
    elif re.search(r"上午", combined):
        plan.start_hint = "上午"

    is_afternoon = "下午" in combined
    time_range = re.search(
        r"(\d{1,2})\s*[点:：]\s*(\d{0,2})?\s*[到至\-~]\s*(\d{1,2})\s*[点:：]?",
        combined,
    )
    if time_range:
        sh, sm, eh = int(time_range.group(1)), time_range.group(2) or "00", int(time_range.group(3))
        if is_afternoon and sh < 12:
            sh += 12
        if is_afternoon and eh < 12:
            eh += 12
        plan.start_hint = f"{sh:02d}:{sm if sm != '00' else '00'}"
        plan.end_hint = f"{eh:02d}:00"
    elif re.search(r"2\s*点\s*到\s*4\s*点|14\s*[点:]\s*到\s*16", combined):
        plan.start_hint = "14:00"
        plan.end_hint = "16:00"

    if "进度" in combined:
        plan.subject = "项目进度会"
    elif "评审" in combined:
        plan.subject = "项目评审会"
    else:
        subject_match = re.search(r"开(.{2,12}?)(?:会议|会)[。！？?]*$", combined)
        if subject_match:
            plan.subject = subject_match.group(1).strip("，, ")
    if not plan.subject:
        plan.subject = "工作会议"

    attendees = re.search(r"参会[人员]*[:：]?\s*([\u4e00-\u9fff、,，\s]{2,30})", combined)
    if attendees:
        plan.attendees = attendees.group(1).strip()

    return plan


def missing_slots(plan: MeetingPlan) -> list[str]:
    missing: list[str] = []
    if not plan.room:
        missing.append("会议室")
    if not plan.date_hint and not plan.start_hint:
        missing.append("会议日期或时段")
    return missing


def is_ready_to_execute(plan: MeetingPlan) -> bool:
    return len(missing_slots(plan)) == 0


def _plan_item(label: str, value: str | None) -> dict[str, str]:
    return {"label": label, "value": value.strip() if value else "—"}


def meeting_plan_confirm_items(plan: MeetingPlan) -> list[dict[str, str]]:
    time_parts = [p for p in (plan.date_hint, plan.start_hint, plan.end_hint) if p]
    time_label = " ".join(time_parts) if time_parts else "—"
    items = [
        _plan_item("会议主题", plan.subject or "工作会议"),
        _plan_item("会议室", f"{plan.room} 会议室" if plan.room else None),
        _plan_item("会议时间", time_label),
    ]
    if plan.attendees:
        items.append(_plan_item("参会人员", plan.attendees))
    return items


def build_meeting_plan_confirm_content(plan: MeetingPlan) -> str:
    lines = [
        "信息已收集完毕，请核对以下会议预约信息：",
        "",
    ]
    for item in meeting_plan_confirm_items(plan):
        lines.append(f"- {item['label']}：{item['value']}")
    lines.extend(
        [
            "",
            "👇 请确认无误后点击下方「确认开始办理」，无需再用文字回复。",
        ]
    )
    return "\n".join(lines)


def build_meeting_plan_confirm_metadata(plan: MeetingPlan) -> dict:
    return {
        "interactive": True,
        "meeting_plan_confirm": {
            "status": "pending",
            "title": f"{plan.subject or '会议'}预约",
            "items": meeting_plan_confirm_items(plan),
        },
    }


def build_meeting_plan_confirm_items(plan: MeetingPlan) -> list[dict[str, str]]:
    time_label = plan.date_hint or ""
    if plan.start_hint and plan.end_hint:
        time_label = f"{plan.date_hint or ''} {plan.start_hint}-{plan.end_hint}".strip()
    elif plan.start_hint:
        time_label = f"{plan.date_hint or ''} {plan.start_hint}".strip()
    return [
        {"label": "会议主题", "value": plan.subject or "工作会议"},
        {"label": "会议室", "value": f"{plan.room} 会议室" if plan.room else "—"},
        {"label": "时间", "value": time_label or "—"},
        {"label": "参会人员", "value": plan.attendees or "待定"},
    ]


def build_meeting_plan_confirm_content(plan: MeetingPlan) -> str:
    lines = [
        "信息已收集完毕，请核对以下会议预约信息：",
        "",
    ]
    for item in build_meeting_plan_confirm_items(plan):
        lines.append(f"- {item['label']}：{item['value']}")
    lines.extend(
        [
            "",
            "👇 请确认无误后点击下方「确认开始办理」，无需再用文字回复。",
        ]
    )
    return "\n".join(lines)


def build_meeting_plan_confirm_metadata(plan: MeetingPlan) -> dict:
    return {
        "interactive": True,
        "meeting_plan_confirm": {
            "status": "pending",
            "title": f"{plan.subject or '会议'}预约",
            "items": build_meeting_plan_confirm_items(plan),
        },
    }


def build_room_selection_content(plan: MeetingPlan, availability: dict) -> str:
    room = plan.room or availability.get("requested_room", "")
    time_label = availability.get("time_label", "")
    reason = availability.get("conflict_reason") or ""
    lines = [
        f"已查询 **{room} 会议室** {time_label} 的预订情况。",
        "",
        reason,
        "",
        "该时段暂不可用。下方为您推荐了同时段可用的会议室，请选择后确认预约。",
    ]
    return "\n".join(lines)


def build_room_selection_metadata(plan: MeetingPlan, availability: dict) -> dict:
    return {
        "interactive": True,
        "room_selection": {
            "status": "pending",
            "subject": plan.subject or "工作会议",
            "requested_room": availability.get("requested_room") or plan.room,
            "time_label": availability.get("time_label", ""),
            "start_time": availability.get("start_time", ""),
            "end_time": availability.get("end_time", ""),
            "conflict_reason": availability.get("conflict_reason"),
            "options": availability.get("alternatives") or [],
        }
    }


def build_execution_summary(plan: MeetingPlan, task_id: str, room: str, time_label: str) -> str:
    return "\n".join(
        [
            f"会议室已确认，已为您启动「{plan.subject or '会议预约'}」办理流程：",
            "",
            "一、会议信息",
            f"- 主题：{plan.subject or '工作会议'}",
            f"- 时间：{time_label}",
            f"- 会议室：**{room}**",
            "",
            "二、后续步骤",
            "- 已生成会议预约表单，请在任务卡片中查看并确认提交",
            "- 确认后将创建国能会议并发送会邀邮件",
            "",
            "请点击下方任务卡片查看详情。",
        ]
    )


def build_task_metadata(plan: MeetingPlan, task_id: str) -> dict:
    return {
        "task_id": task_id,
        "task_title": f"{plan.subject or '会议'}预约",
        "progress": "1/3",
        "progress_percent": 33,
        "steps_desc": "会议室确认 · 会议预约 · 用户确认",
    }
