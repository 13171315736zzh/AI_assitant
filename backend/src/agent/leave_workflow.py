"""请假申请流程：槽位收集与确认。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from src.agent.session_context import is_plan_revision_text, merge_user_texts

_LEAVE_INTENT = re.compile(
    r"请假|休假|请\s*(?:病|事|年|调休|婚|产|丧)|"
    r"病假|事假|年假|调休|婚假|产假|丧假|"
    r"在家休息|需要休息"
)
_WORKPACKAGE_CONTEXT = re.compile(r"工包|工时|填报|人天|人日|填到|填在|填神|填雁")
_LEAVE_TYPE_PATTERN = re.compile(r"(病假|事假|年假|调休|婚假|产假|丧假|其他假|其他)")
_DATE_RANGE_PATTERN = re.compile(
    r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?\s*(?:到|至|—|-)\s*(\d{1,2})\s*月?\s*(\d{1,2})\s*[日号]?"
)
_SINGLE_DATE_PATTERN = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?")
_WEEKDAY_PATTERN = re.compile(r"(?:本|这|下)?\s*(周|星期)([一二三四五六日天])")
_DURATION_PATTERN = re.compile(r"(?:请|休|放)\s*(\d+)\s*天")
_WEEKDAY_MAP = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}
_PERIOD_HALF = re.compile(r"半天|半日")
_PERIOD_AM = re.compile(r"上午|早上|晨")
_PERIOD_PM = re.compile(r"下午|午后")


@dataclass
class LeavePlan:
    leave_type: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    start_period: str = "全天"
    end_period: str = "全天"
    reason: str | None = None
    attachment_name: str | None = None
    raw_goal: str = ""


def is_leave_workflow_intent(text: str) -> bool:
    from src.agent.workflow_queue import split_intent_segments

    segments = split_intent_segments(text)
    for segment in segments:
        if not _LEAVE_INTENT.search(segment):
            continue
        if re.search(r"请假申请|补.*?请假|申请.*?假|请.*?假条", segment):
            return True
        if _WORKPACKAGE_CONTEXT.search(segment):
            continue
        return True
    return False


def is_leave_plan_update(text: str) -> bool:
    if is_plan_revision_text(text):
        return True
    if _LEAVE_INTENT.search(text):
        return True
    if _DATE_RANGE_PATTERN.search(text) or _SINGLE_DATE_PATTERN.search(text):
        return True
    if _WEEKDAY_PATTERN.search(text) or re.search(r"明天|后天", text):
        return True
    if re.search(r"原因|事由|因为|由于|附件|假条|医院|事故", text):
        return True
    return False


def _weekday_to_date(weekday_name: str, *, next_week: bool = False, today: date | None = None) -> date:
    today = today or date.today()
    target = _WEEKDAY_MAP.get(weekday_name, 0)
    current = today.weekday()
    delta = (target - current) % 7
    if delta == 0 and not next_week:
        delta = 7
    if next_week:
        delta = (target - current) % 7 + 7
    return today + timedelta(days=delta)


def _iso(d: date) -> str:
    return d.isoformat()


def _resolve_period(text: str) -> tuple[str, str]:
    if _PERIOD_HALF.search(text):
        if _PERIOD_AM.search(text):
            return "上午", "上午"
        if _PERIOD_PM.search(text):
            return "下午", "下午"
        return "下午", "下午"
    if _PERIOD_AM.search(text) and not _PERIOD_PM.search(text):
        if re.search(r"请假|休假|休息|假", text):
            return "上午", "上午"
    if _PERIOD_PM.search(text) and not _PERIOD_AM.search(text):
        if re.search(r"请假|休假|休息|假", text):
            return "下午", "下午"
    return "全天", "全天"


def _leave_focus_text(combined: str) -> str:
    from src.agent.workflow_queue import split_intent_segments

    for segment in split_intent_segments(combined):
        if not _LEAVE_INTENT.search(segment):
            continue
        match = re.search(r"(.+?请假[^，,]*)", segment)
        if match:
            return match.group(1).strip()
        for sep in ("会议", "开会", "国能会"):
            if sep in segment:
                return segment.split(sep, 1)[0].rstrip("，, ")
        return segment
    return combined


def _parse_dates(combined: str) -> tuple[str | None, str | None, str, str]:
    today = date.today()
    start_period, end_period = _resolve_period(_leave_focus_text(combined))

    range_match = _DATE_RANGE_PATTERN.search(combined)
    if range_match:
        month1, day1, month2, day2 = map(int, range_match.groups())
        year = today.year
        start = date(year, month1, day1)
        end = date(year, month2, day2)
        if end < start:
            end = date(year + 1, month2, day2)
        return _iso(start), _iso(end), start_period, end_period

    if re.search(r"昨天", combined):
        d = today - timedelta(days=1)
        return _iso(d), _iso(d), start_period, end_period

    if re.search(r"前天", combined):
        d = today - timedelta(days=2)
        return _iso(d), _iso(d), start_period, end_period

    if re.search(r"今天|今日", combined):
        return _iso(today), _iso(today), start_period, end_period

    if re.search(r"明天", combined):
        d = today + timedelta(days=1)
        return _iso(d), _iso(d), start_period, end_period

    if re.search(r"后天", combined):
        d = today + timedelta(days=2)
        return _iso(d), _iso(d), start_period, end_period

    weekday_match = _WEEKDAY_PATTERN.search(combined)
    if weekday_match:
        matched = weekday_match.group(0)
        next_week = matched.startswith("下") or "下周" in combined
        weekday_char = weekday_match.group(2)
        d = _weekday_to_date(weekday_char, next_week=next_week, today=today)
        return _iso(d), _iso(d), start_period, end_period

    single_match = _SINGLE_DATE_PATTERN.search(combined)
    if single_match:
        month, day = map(int, single_match.groups())
        year = today.year
        d = date(year, month, day)
        if d < today - timedelta(days=30):
            d = date(year + 1, month, day)
        return _iso(d), _iso(d), start_period, end_period

    duration_match = _DURATION_PATTERN.search(combined)
    if duration_match:
        days = int(duration_match.group(1))
        start = today + timedelta(days=1)
        end = start + timedelta(days=max(days - 1, 0))
        return _iso(start), _iso(end), start_period, end_period

    return None, None, start_period, end_period


def _parse_leave_type(combined: str) -> str | None:
    match = _LEAVE_TYPE_PATTERN.search(combined)
    if match:
        value = match.group(1)
        return "其他" if value in ("其他假",) else value
    if re.search(r"感冒|发烧|咳嗽|生病|身体不适|不舒服|医院|受伤", combined):
        return "病假"
    if "病" in combined and "请假" in combined:
        return "病假"
    if "事" in combined and "请假" in combined:
        return "事假"
    return None


def _parse_reason(combined: str) -> str | None:
    from src.agent.workflow_queue import split_intent_segments

    explicit_patterns = [
        r"(?:原因|事由|因为|由于)[:：是为]?\s*(.{2,120}?)(?:[。！？?]|$)",
    ]
    colloquial_patterns = [
        r"(?:我)?(?:今天|明天|后天|昨日|昨天)?(.+?)(?:需要|要)(?:申请)?请假",
    ]
    for segment in split_intent_segments(combined):
        if not _LEAVE_INTENT.search(segment):
            continue
        for pattern in explicit_patterns:
            match = re.search(pattern, segment)
            if match:
                reason = match.group(1).strip("，, ")
                if reason and len(reason) >= 2:
                    return reason
        for pattern in colloquial_patterns:
            match = re.search(pattern, segment)
            if match:
                reason = re.sub(r"^我", "", match.group(1)).strip("，, ")
                if reason and len(reason) >= 2:
                    return reason
    return None


def build_leave_plan(messages) -> LeavePlan:
    combined = merge_user_texts(
        [
            record.content.strip()
            for record in messages
            if getattr(record, "role", None) == "user" and record.content.strip()
        ]
    )
    plan = LeavePlan(raw_goal=combined[:500])
    plan.leave_type = _parse_leave_type(combined)
    plan.date_start, plan.date_end, plan.start_period, plan.end_period = _parse_dates(combined)
    plan.reason = _parse_reason(combined)
    if not plan.leave_type:
        plan.leave_type = "事假"
    return plan


def missing_slots(plan: LeavePlan) -> list[str]:
    missing: list[str] = []
    if not plan.date_start or not plan.date_end:
        missing.append("请假时间")
    return missing


def is_ready_to_execute(plan: LeavePlan) -> bool:
    return len(missing_slots(plan)) == 0


def compute_leave_days(plan: LeavePlan) -> float:
    if not plan.date_start or not plan.date_end:
        return 0.0
    start = date.fromisoformat(plan.date_start)
    end = date.fromisoformat(plan.date_end)
    if start == end:
        if plan.start_period == plan.end_period == "全天":
            return 1.0
        if plan.start_period != plan.end_period:
            return 1.0
        return 0.5
    days = (end - start).days + 1
    return float(max(days, 1))


def format_leave_period(plan: LeavePlan) -> str:
    if not plan.date_start or not plan.date_end:
        return "—"
    start = date.fromisoformat(plan.date_start)
    end = date.fromisoformat(plan.date_end)
    if start == end:
        label = f"{start.month}月{start.day}日"
        if plan.start_period != "全天":
            label += f"（{plan.start_period}）"
        return label
    return f"{start.month}月{start.day}日 至 {end.month}月{end.day}日"


def _plan_item(label: str, value: str | None) -> dict[str, str]:
    return {"label": label, "value": value.strip() if value else "—"}


def build_leave_plan_confirm_items(plan: LeavePlan) -> list[dict[str, str]]:
    days = compute_leave_days(plan)
    days_label = f"{days:g} 天" if days != int(days) else f"{int(days)} 天"
    return [
        _plan_item("请假类型", plan.leave_type),
        _plan_item("请假时间", format_leave_period(plan)),
        _plan_item("请假天数", days_label),
        _plan_item("请假事由", plan.reason),
    ]


def build_leave_plan_confirm_content(plan: LeavePlan, *, updated: bool = False) -> str:
    intro = (
        "已根据您补充的信息更新请假申请，请核对："
        if updated
        else "信息已收集完毕，请核对以下请假申请信息："
    )
    lines = [intro, ""]
    for item in build_leave_plan_confirm_items(plan):
        lines.append(f"- {item['label']}：{item['value']}")
    if plan.date_start and plan.reason:
        footer = "👇 如需调整请在下方卡片中修改，完成后点击「确认提交请假」。"
    elif plan.date_start:
        footer = "👇 请在下方卡片中核对请假信息并补充事由，完成后点击「确认提交请假」。"
    else:
        footer = "👇 请在下方卡片中填写请假时间与事由，完成后点击「确认提交请假」。"
    lines.extend(["", footer])
    return "\n".join(lines)


def build_leave_plan_confirm_metadata(plan: LeavePlan) -> dict:
    return {
        "interactive": True,
        "leave_plan_confirm": {
            "status": "pending",
            "title": "请假申请",
            "items": build_leave_plan_confirm_items(plan),
            "leave_type": plan.leave_type,
            "date_start": plan.date_start,
            "date_end": plan.date_end,
            "start_period": plan.start_period,
            "end_period": plan.end_period,
            "reason": plan.reason,
            "attachment_name": plan.attachment_name,
            "requires_reason": not bool(plan.reason),
        },
    }


def build_execution_summary(plan: LeavePlan, task_id: str) -> str:
    return (
        f"「{plan.leave_type or '请假'}」信息已确认。"
        "请点击中间选项卡打开划窗，核对步骤后前往 OA 提交；下方可继续办理下一事项。"
    )


def build_task_metadata(plan: LeavePlan, task_id: str) -> dict:
    return {
        "task_id": task_id,
        "task_title": f"{plan.leave_type or '请假'}申请",
        "progress": "1/2",
        "progress_percent": 50,
        "steps_desc": "请假申请 · 用户确认",
        "confirmed_items": build_leave_plan_confirm_items(plan),
    }


def apply_leave_plan_draft(plan: LeavePlan, draft: dict | None) -> LeavePlan:
    """合并确认卡片填写/点选；与对话或输入框解析冲突时，以卡片非空字段为准。"""
    if not draft:
        return plan

    leave_type = str(draft.get("leave_type") or "").strip()
    if leave_type:
        plan.leave_type = leave_type

    date_start = str(draft.get("date_start") or "").strip()
    if date_start:
        plan.date_start = date_start

    date_end = str(draft.get("date_end") or "").strip()
    if date_end:
        plan.date_end = date_end

    start_period = str(draft.get("start_period") or "").strip()
    if start_period:
        plan.start_period = start_period

    end_period = str(draft.get("end_period") or "").strip()
    if end_period:
        plan.end_period = end_period

    if draft.get("reason") is not None:
        reason = str(draft.get("reason") or "").strip()
        plan.reason = reason or None

    attachment_name = str(draft.get("attachment_name") or "").strip()
    if attachment_name:
        plan.attachment_name = attachment_name

    return plan
