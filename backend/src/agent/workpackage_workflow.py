"""工包/工时填报流程：槽位收集、冲突检测与确认。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.agent.workpackage_period import has_month_week_intent, parse_month_week_period
from src.agent.session_context import is_plan_revision_text, merge_user_texts
from src.integrations.work_calendar import list_workdays

_WORKPACKAGE_INTENT = re.compile(r"工包|工时|填报|人天|人日")
_PROJECT_PATTERN = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9·]{2,20}(?:售前|售后|可视化|能源|数据|大模型)?项目)"
)
_PROJECT_HINT_PATTERN = re.compile(
    r"(?:"
    r"填(?:报到|到|在|报)?|"
    r"都(?:要|需)?填(?:报|到|在)?|"
    r"做在|做到"
    r")\s*[「\"']?([\u4e00-\u9fffA-Za-z0-9·]{2,24})"
)
_THIS_WEEK_PATTERN = re.compile(r"本周")
_LAST_WEEK_PATTERN = re.compile(r"上周")
_KNOWN_PERIOD_HINTS = frozenset({"本周", "上周"})
_WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
_WEEKDAY_TO_INDEX = {name: idx for idx, name in enumerate(_WEEKDAY_NAMES)}
DEFAULT_HOURS_PER_DAY = 8.0
FULL_WEEK_DAYS = 5.0


@dataclass
class LeaveSlot:
    weekday: int
    period: str
    hours_off: float


@dataclass
class WorkpackagePlan:
    project: str | None = None
    total_person_days: float | None = None
    fill_days: float | None = None
    period_hint: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    full_week: bool = False
    hours_per_day: float = DEFAULT_HOURS_PER_DAY
    content: str | None = None
    raw_goal: str = ""
    project_options: list[str] = field(default_factory=list)
    leave_slots: list[LeaveSlot] = field(default_factory=list)
    project_from_mapping: bool = False
    hours_confirmed: bool = False
    all_days_eight_hours: bool | None = None


def is_workpackage_workflow_intent(text: str) -> bool:
    from src.agent.workflow_queue import split_intent_segments

    segments = split_intent_segments(text)
    for segment in segments:
        if not _WORKPACKAGE_INTENT.search(segment):
            continue
        if _PROJECT_PATTERN.search(segment):
            return True
        if _THIS_WEEK_PATTERN.search(segment) or _LAST_WEEK_PATTERN.search(segment):
            return True
        if has_month_week_intent(segment):
            return True
        if _PROJECT_HINT_PATTERN.search(segment):
            return True
    return False


def compute_last_week_range(today: date | None = None) -> tuple[date, date, int]:
    """上周一至上周五。"""
    today = today or date.today()
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)
    last_friday = last_monday + timedelta(days=4)
    return last_monday, last_friday, 5


def compute_this_week_range(
    today: date | None = None,
    *,
    full_week: bool = False,
) -> tuple[date, date, int]:
    """本周范围：默认周一至今天；整周模式为周一至周五。"""
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=4) if full_week else today
    calendar_days = (week_end - week_start).days + 1
    return week_start, week_end, calendar_days


def wants_full_week(combined: str) -> bool:
    return bool(
        re.search(
            r"整周|全周|5\s*天|五个工作日|周一到周五|周一到周五|每天(?:都)?(?:要|需)?填|全都填",
            combined,
        )
    )


_WEEKDAY_REF_PATTERN = re.compile(
    r"(?:那个|那|这|本)?\s*周([一二三四五六日])|"
    r"周([一二三四五六日])"
)
_HALF_DAY_PATTERN = re.compile(r"半(?:天|日)|0\.5\s*个?\s*人?[天日]")
_LEAVE_INTENT_PATTERN = re.compile(r"请?(?:半)?天?假|休假|休息")


_WEEKDAY_CHAR_TO_INDEX = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}


def _weekday_from_token(token: str) -> int | None:
    if not token:
        return None
    token = token.strip()
    if token in _WEEKDAY_TO_INDEX:
        return _WEEKDAY_TO_INDEX[token]
    if token.startswith("周") and len(token) == 2:
        return _WEEKDAY_CHAR_TO_INDEX.get(token[1])
    return _WEEKDAY_CHAR_TO_INDEX.get(token)


def extract_weekday_reference(text: str) -> int | None:
    """从「那个周四」「周四」等表述提取 weekday index。"""
    match = _WEEKDAY_REF_PATTERN.search(text)
    if not match:
        return None
    token = match.group(1) or match.group(2)
    return _weekday_from_token(token)


def _parse_half_day_detail(text: str) -> tuple[bool, str | None]:
    """识别半天请假；返回 (是否半天, 上午/下午/None)。"""
    if not _HALF_DAY_PATTERN.search(text):
        if not re.search(r"请假\s*半天|半天\s*假", text):
            return False, None
    if "上午" in text and "下午" not in text:
        return True, "上午"
    if "下午" in text and "上午" not in text:
        return True, "下午"
    return True, None


def _parse_explicit_leave_slots(text: str) -> list[LeaveSlot]:
    """单句内完整表达的请假（含 weekday）。"""
    slots: list[LeaveSlot] = []
    seen: set[tuple[int, str]] = set()
    half_day = DEFAULT_HOURS_PER_DAY / 2

    def add(weekday: int, period: str, hours_off: float) -> None:
        key = (weekday, period)
        if key in seen:
            return
        seen.add(key)
        slots.append(LeaveSlot(weekday=weekday, period=period, hours_off=hours_off))

    leave_patterns = [
        r"(?:预计|可能|也许|应该)?\s*(?:我)?(?:那个|那|这)?\s*周?([一二三四五六日])\s*(上午|下午)?\s*(?:会|要|需要)?\s*(?:请?(?:半)?天?假|休假|休息)",
        r"(?:那个|那|这)?\s*周([一二三四五六日])\s*(上午|下午)?\s*(?:会|要|需要)?\s*(?:请?(?:半)?天?假|休假|休息)",
        r"(周[一二三四五六日])\s*(上午|下午)\s*(?:会|要|需要)?\s*(?:请?(?:半)?天?假|休假|休息)",
        r"(周[一二三四五六日])(?:是|都)?(?:放?假|休(?:息|假)?)",
    ]
    is_half, half_period = _parse_half_day_detail(text)
    for pattern in leave_patterns:
        for match in re.finditer(pattern, text):
            raw = match.group(1)
            weekday = _weekday_from_token(raw)
            if weekday is None:
                continue
            period = "全天"
            if match.lastindex and match.lastindex >= 2 and match.group(2):
                period = match.group(2)
            if is_half and period == "全天":
                period = half_period or "半天"
            if period in ("上午", "下午", "半天"):
                add(weekday, period, half_day)
            else:
                add(weekday, "全天", DEFAULT_HOURS_PER_DAY)
    return slots


def _parse_relative_day_leave_slots(text: str, today: date | None = None) -> list[LeaveSlot]:
    """解析「昨天/前天 + 上午/下午 + 请假」类表述。"""
    today = today or date.today()
    if not _LEAVE_INTENT_PATTERN.search(text):
        return []

    half_day = DEFAULT_HOURS_PER_DAY / 2
    relative_patterns = (
        (r"大前天", 3),
        (r"前天", 2),
        (r"昨天", 1),
    )
    for pattern, days_ago in relative_patterns:
        if not re.search(pattern, text):
            continue
        weekday = (today - timedelta(days=days_ago)).weekday()
        is_half, half_period = _parse_half_day_detail(text)
        if not is_half and ("上午" in text or "下午" in text):
            is_half = True
            half_period = "上午" if "上午" in text else "下午"
        if is_half:
            period = half_period or "半天"
            return [LeaveSlot(weekday=weekday, period=period, hours_off=half_day)]
        return [LeaveSlot(weekday=weekday, period="全天", hours_off=DEFAULT_HOURS_PER_DAY)]
    return []


def parse_leave_requests_from_messages(messages) -> list[LeaveSlot]:
    """结合多轮对话上下文，合并/细化请假安排。"""
    by_weekday: dict[int, LeaveSlot] = {}
    last_weekday: int | None = None
    half_day = DEFAULT_HOURS_PER_DAY / 2

    def upsert(weekday: int, period: str, hours_off: float) -> None:
        nonlocal last_weekday
        by_weekday[weekday] = LeaveSlot(
            weekday=weekday,
            period=period,
            hours_off=hours_off,
        )
        last_weekday = weekday

    user_messages = [
        record.content.strip()
        for record in messages
        if getattr(record, "role", None) == "user" and record.content.strip()
    ]

    for text in user_messages:
        weekday_ref = extract_weekday_reference(text)

        relative_slots = _parse_relative_day_leave_slots(text)
        for slot in relative_slots:
            upsert(slot.weekday, slot.period, slot.hours_off)

        explicit_slots = _parse_explicit_leave_slots(text)
        for slot in explicit_slots:
            upsert(slot.weekday, slot.period, slot.hours_off)

        if weekday_ref is not None:
            last_weekday = weekday_ref
            if _LEAVE_INTENT_PATTERN.search(text) and weekday_ref not in by_weekday:
                is_half, half_period = _parse_half_day_detail(text)
                if is_half:
                    upsert(weekday_ref, half_period or "半天", half_day)
                else:
                    upsert(weekday_ref, "全天", DEFAULT_HOURS_PER_DAY)

        is_half, half_period = _parse_half_day_detail(text)
        if is_half and last_weekday is not None:
            upsert(last_weekday, half_period or "半天", half_day)
        elif (
            _LEAVE_INTENT_PATTERN.search(text)
            and last_weekday is not None
            and weekday_ref is None
            and not explicit_slots
            and not relative_slots
        ):
            upsert(last_weekday, "全天", DEFAULT_HOURS_PER_DAY)

    return list(by_weekday.values())


def parse_leave_requests(text: str) -> list[LeaveSlot]:
    from types import SimpleNamespace

    return parse_leave_requests_from_messages(
        [SimpleNamespace(role="user", content=text)]
    )


def mentions_leave_adjustment(text: str) -> bool:
    if parse_leave_requests(text):
        return True
    if extract_weekday_reference(text) and _LEAVE_INTENT_PATTERN.search(text):
        return True
    if _HALF_DAY_PATTERN.search(text) or re.search(r"请假\s*半天|半天\s*假", text):
        return True
    return bool(_LEAVE_INTENT_PATTERN.search(text))


def _format_leave_slot(slot: LeaveSlot) -> str:
    label = _WEEKDAY_NAMES[slot.weekday]
    if slot.period == "全天":
        return f"{label}全天请假"
    if slot.period == "半天":
        return f"{label}请假半天"
    return f"{label}{slot.period}请假"


def is_workpackage_plan_update(text: str) -> bool:
    """待确认工时单存在时，识别用户的补充/修正说明。"""
    if mentions_leave_adjustment(text):
        return True
    if is_plan_revision_text(text):
        return True
    if hours_explicitly_confirmed_in_text(text):
        return True
    if has_month_week_intent(text):
        return True
    if _THIS_WEEK_PATTERN.search(text) or _LAST_WEEK_PATTERN.search(text):
        return True
    if _PROJECT_HINT_PATTERN.search(text) or _PROJECT_PATTERN.search(text):
        return True
    return bool(re.search(r"改|换|调整|补充|更新", text))


def format_date_range(start: date, end: date) -> str:
    return f"{start.isoformat()} ~ {end.isoformat()}"


def _leave_for_weekday(leave_slots: list[LeaveSlot], weekday: int) -> list[LeaveSlot]:
    return [slot for slot in leave_slots if slot.weekday == weekday]


def _hours_for_workday(
    weekday: int,
    leave_slots: list[LeaveSlot],
    hours_per_day: float,
) -> tuple[float, str] | None:
    """返回 (hours, period)；None 表示整日无需填报。"""
    leaves = _leave_for_weekday(leave_slots, weekday)
    if any(slot.period == "全天" for slot in leaves):
        return None

    half_day = hours_per_day / 2
    morning_off = any(slot.period == "上午" for slot in leaves)
    afternoon_off = any(slot.period == "下午" for slot in leaves)
    half_day_off = any(slot.period == "半天" for slot in leaves)

    if morning_off and afternoon_off:
        return None
    if half_day_off:
        return half_day, "上午"
    if morning_off:
        return half_day, "下午"
    if afternoon_off:
        return half_day, "上午"
    return hours_per_day, "全天"


def compute_period_person_days(
    date_start: str,
    date_end: str,
    *,
    leave_slots: list[LeaveSlot] | None = None,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
) -> float:
    """按工作日历与请假安排，统计区间内可填报的人天。"""
    return round(
        sum(
            entry["person_days"]
            for entry in compute_period_fill_entries(
                date_start,
                date_end,
                leave_slots=leave_slots,
                hours_per_day=hours_per_day,
            )
        ),
        2,
    )


def compute_period_fill_entries(
    date_start: str,
    date_end: str,
    *,
    leave_slots: list[LeaveSlot] | None = None,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
) -> list[dict]:
    """按工作日历与请假安排，返回区间内各可填报日期明细。"""
    leave_slots = leave_slots or []
    start = date.fromisoformat(date_start)
    end = date.fromisoformat(date_end)
    entries: list[dict] = []
    for day in list_workdays(start, end):
        hours_info = _hours_for_workday(day.weekday(), leave_slots, hours_per_day)
        if hours_info is None:
            continue
        hours, period = hours_info
        person_days = round(hours / hours_per_day, 2) if hours_per_day else 0.0
        entries.append(
            {
                "day_date": day.isoformat(),
                "day_label": _WEEKDAY_NAMES[day.weekday()],
                "period": period,
                "person_days": person_days,
                "hours": hours,
            }
        )
    return entries


def format_fill_dates_display(entries: list[dict]) -> str | None:
    if not entries:
        return None
    parts: list[str] = []
    for entry in entries:
        day = date.fromisoformat(entry["day_date"])
        label = f"{day.month}月{day.day}日（{entry.get('day_label') or _WEEKDAY_NAMES[day.weekday()]}）"
        person_days = entry.get("person_days", 1)
        period = entry.get("period")
        if person_days < 1:
            label += "·半天"
        elif period and period != "全天":
            label += f"·{period}"
        parts.append(label)
    return "、".join(parts)


def format_person_days(value: float | None) -> str | None:
    if value is None:
        return None
    if value == int(value):
        return f"{int(value)} 人·天"
    return f"{value:g} 人·天"


def has_resolved_period(plan: WorkpackagePlan) -> bool:
    return bool(plan.date_start and plan.date_end)


def hours_explicitly_confirmed_in_text(text: str) -> bool:
    return bool(
        re.search(
            r"每?天(?:的)?(?:工时)?都?(?:是|为)?\s*8\s*小时|"
            r"都是\s*8\s*小时|"
            r"8\s*小时/?天|"
            r"每天\s*8\s*小时",
            text,
        )
    )


def normalize_workpackage_plan(plan: WorkpackagePlan) -> WorkpackagePlan:
    combined = plan.raw_goal
    month_week = parse_month_week_period(combined)
    if month_week:
        week_start, week_end, label = month_week
        plan.period_hint = label
        plan.full_week = True
        plan.date_start = week_start.isoformat()
        plan.date_end = week_end.isoformat()
    elif "上周" in combined:
        plan.period_hint = "上周"
        plan.full_week = True
        week_start, week_end, _ = compute_last_week_range()
        plan.date_start = week_start.isoformat()
        plan.date_end = week_end.isoformat()
    elif plan.period_hint == "本周" or (plan.period_hint is None and "本周" in combined):
        plan.period_hint = plan.period_hint or "本周"
        plan.full_week = plan.full_week or wants_full_week(combined)
        week_start, week_end, _ = compute_this_week_range(full_week=plan.full_week)
        plan.date_start = week_start.isoformat()
        plan.date_end = week_end.isoformat()

    if hours_explicitly_confirmed_in_text(combined):
        plan.hours_per_day = DEFAULT_HOURS_PER_DAY
        plan.all_days_eight_hours = True
        plan.hours_confirmed = True

    if has_resolved_period(plan):
        plan.fill_days = compute_period_person_days(
            plan.date_start,
            plan.date_end,
            leave_slots=plan.leave_slots,
            hours_per_day=plan.hours_per_day,
        )
    return plan


def build_workpackage_plan(messages) -> WorkpackagePlan:
    combined = merge_user_texts(
        [
            record.content.strip()
            for record in messages
            if getattr(record, "role", None) == "user" and record.content.strip()
        ]
    )
    plan = WorkpackagePlan(raw_goal=combined[:200])

    proj = _PROJECT_PATTERN.search(combined)
    if proj:
        plan.project = proj.group(1)

    hint = _PROJECT_HINT_PATTERN.search(combined)
    if hint and not plan.project:
        plan.project = hint.group(1).strip("上项目 ")

    yanbao = re.search(r"[燕雁]宝(?:售前|售后)?项目", combined)
    if yanbao:
        plan.project = yanbao.group(0)

    total_match = re.search(r"(\d+(?:\.\d+)?)\s*个?\s*人[天日]", combined)
    if total_match:
        plan.total_person_days = float(total_match.group(1))

    fill_match = re.search(r"(\d+(?:\.\d+)?)\s*天", combined)
    if fill_match:
        plan.fill_days = float(fill_match.group(1))
    elif re.search(r"本周.*5\s*天|5\s*天.*本周|本周.*五个工作日", combined):
        plan.fill_days = FULL_WEEK_DAYS

    if "上周" in combined:
        plan.period_hint = "上周"
    elif "本周" in combined:
        plan.period_hint = "本周"
    elif "本月" in combined:
        plan.period_hint = "本月"

    hours_match = re.search(r"(\d+(?:\.\d+)?)\s*小时", combined)
    if hours_match:
        plan.hours_per_day = float(hours_match.group(1))

    content_match = re.search(r"(?:内容|工作)[：:]\s*(.{2,40})", combined)
    if content_match:
        plan.content = content_match.group(1).strip()

    plan.leave_slots = parse_leave_requests_from_messages(messages)
    return normalize_workpackage_plan(plan)


def apply_project_options(plan: WorkpackagePlan, options: list[str]) -> WorkpackagePlan:
    plan.project_options = options
    if not plan.project and len(options) == 1:
        plan.project = options[0]
    return plan


def missing_slots(plan: WorkpackagePlan) -> list[str]:
    missing: list[str] = []
    if plan.fill_days is None and not has_resolved_period(plan):
        missing.append("填报天数")
    if not plan.project and not plan.project_options:
        missing.append("项目名称")
    return missing


def needs_project_selection(plan: WorkpackagePlan) -> bool:
    return not plan.project and len(plan.project_options) > 1


def is_ready_to_execute(plan: WorkpackagePlan) -> bool:
    if needs_project_selection(plan):
        return False
    return len(missing_slots(plan)) == 0


def can_auto_submit(plan: WorkpackagePlan) -> bool:
    """项目、周期、工时均已明确时，可跳过确认直接生成填报任务。"""
    if not is_ready_to_execute(plan):
        return False
    if not has_resolved_period(plan):
        return False
    if not plan.hours_confirmed:
        return False
    return bool(plan.project)


def _plan_item(label: str, value: str | int | float | None) -> dict[str, str]:
    if value is None or value == "":
        display = "—"
    else:
        display = str(value)
    return {"label": label, "value": display}


def workpackage_plan_confirm_items(plan: WorkpackagePlan) -> list[dict[str, str]]:
    period_display = plan.period_hint or "本周"
    fill_entries: list[dict] = []
    if plan.date_start and plan.date_end:
        period_display = format_date_range(
            date.fromisoformat(plan.date_start),
            date.fromisoformat(plan.date_end),
        )
        fill_entries = compute_period_fill_entries(
            plan.date_start,
            plan.date_end,
            leave_slots=plan.leave_slots,
            hours_per_day=plan.hours_per_day,
        )
    items = [
        _plan_item("项目名称", plan.project or ("请选择" if plan.project_options else None)),
        _plan_item("填报天数", format_person_days(plan.fill_days)),
        _plan_item("填报周期", period_display),
    ]
    fill_dates_display = format_fill_dates_display(fill_entries)
    if fill_dates_display:
        items.append(_plan_item("填报日期", fill_dates_display))
    if plan.hours_confirmed:
        items.append(_plan_item("每日工时", f"{plan.hours_per_day:g} 小时"))
    if plan.total_person_days:
        items.append(_plan_item("项目总人天", f"{plan.total_person_days:g} 人天"))
    if plan.content:
        items.append(_plan_item("工作内容", plan.content))
    if plan.leave_slots:
        leave_desc = "；".join(
            _format_leave_slot(s)
            for s in plan.leave_slots
        )
        items.append(_plan_item("请假安排", leave_desc))
    return items


def build_workpackage_plan_confirm_content(plan: WorkpackagePlan, *, updated: bool = False) -> str:
    period_display = plan.period_hint or "本周"
    if plan.date_start and plan.date_end:
        period_display = format_date_range(
            date.fromisoformat(plan.date_start),
            date.fromisoformat(plan.date_end),
        )
    fill_entries = (
        compute_period_fill_entries(
            plan.date_start,
            plan.date_end,
            leave_slots=plan.leave_slots,
            hours_per_day=plan.hours_per_day,
        )
        if plan.date_start and plan.date_end
        else []
    )
    if plan.fill_days is not None:
        fill_days_line = f"- 填报天数：**{format_person_days(plan.fill_days)}**"
    else:
        fill_days_line = "- 填报天数：—"
    intro = (
        "已根据您补充的信息更新填报计划，请核对："
        if updated
        else "信息已齐全，请核对以下工时填报信息："
    )
    lines = [
        intro,
        "",
        f"- 项目：**{plan.project or '待选择'}**",
        fill_days_line,
        f"- 填报周期：**{period_display}**",
    ]
    fill_dates_display = format_fill_dates_display(fill_entries)
    if fill_dates_display:
        lines.append(f"- 填报日期：**{fill_dates_display}**")
    lines.extend(["",])
    if not plan.hours_confirmed:
        hours_hint = (
            "**待确认除已标注请假外，其余日期每天填报8小时**"
            if plan.leave_slots
            else "**待确认上述日期中每天填报8小时（没有请假）**"
        )
        lines.append(f"- 每日工时：{hours_hint}")
        lines.append("")
    else:
        lines.append(f"- 每日工时：**{plan.hours_per_day:g} 小时**")
        lines.append("")
    if needs_project_selection(plan):
        lines.append("👇 请先点击选择项目，再点击「确认开始办理」。")
    elif not plan.project:
        lines.append("👇 请先补充项目名称（可直接在对话中说明），再点击「确认开始办理」。")
    else:
        lines.append("👇 请确认项目、周期与每日工时后点击「确认开始办理」。")
    return "\n".join(lines)


def build_workpackage_plan_confirm_metadata(plan: WorkpackagePlan) -> dict:
    fill_entries = (
        compute_period_fill_entries(
            plan.date_start,
            plan.date_end,
            leave_slots=plan.leave_slots,
            hours_per_day=plan.hours_per_day,
        )
        if plan.date_start and plan.date_end
        else []
    )
    hours_question = (
        "请确认除已标注请假外，其余日期每天填报8小时"
        if plan.leave_slots
        else "请确认上述日期中每天填报8小时（没有请假）"
    )
    return {
        "interactive": True,
        "workpackage_plan_confirm": {
            "status": "pending",
            "title": f"{plan.project or plan.period_hint or '工时'}填报",
            "items": workpackage_plan_confirm_items(plan),
            "project_options": plan.project_options,
            "selected_project": plan.project,
            "date_start": plan.date_start,
            "date_end": plan.date_end,
            "fill_dates": fill_entries,
            "hours_per_day": plan.hours_per_day,
            "hours_confirmed": plan.hours_confirmed,
            "hours_question": hours_question,
            "hour_presets": [
                {"label": "4 小时/天", "value": 4},
                {"label": "6 小时/天", "value": 6},
                {"label": "10 小时/天", "value": 10},
            ],
            "requires_project": not plan.project and not plan.project_options,
        },
    }


def build_workpackage_confirm_content(plan: WorkpackagePlan, fill_plan: dict) -> str:
    conflicts = fill_plan.get("conflicts") or []
    skipped = fill_plan.get("skipped_days") or []
    requested = fill_plan.get("requested_days", plan.fill_days)
    period_label = fill_plan.get("period_label") or plan.period_hint or "本周"
    total_hours = fill_plan.get("total_hours")
    lines = [
        f"已按 **{period_label}** 排班与请假信息生成填报计划，项目 **{plan.project}** 共 {requested:g} 个工作日。",
        f"每个工作日默认 **{plan.hours_per_day:g} 小时**（已扣除请假时段）。",
        "",
    ]
    if skipped:
        lines.append("**以下日期为非工作日/假期，已自动跳过：**")
        for item in skipped:
            lines.append(f"- {item.get('day_date')} {item.get('day_label', '')}（{item.get('reason')}）")
        lines.append("")
    if plan.leave_slots:
        lines.append("**已识别请假：**")
        for slot in plan.leave_slots:
            lines.append(f"- {_format_leave_slot(slot)}")
        lines.append("")
    if conflicts:
        for c in conflicts:
            lines.append(
                f"- **{c.get('day_label')}**{c.get('period')}已使用 "
                f"**{c.get('existing_project')}** 完成 {c.get('hours', 4):g} 小时填报"
            )
        lines.append("")
    if total_hours is not None:
        lines.append(f"预计合计 **{total_hours:g} 小时**，请勾选下方日期并确认。")
    else:
        lines.append("请勾选下方日期并确认填报计划。")
    return "\n".join(lines)


def build_workpackage_confirm_metadata(plan: WorkpackagePlan, fill_plan: dict) -> dict:
    return {
        "interactive": True,
        "workpackage_confirm": {
            "status": "pending",
            "project": plan.project or "",
            "period_label": fill_plan.get("period_label") or plan.period_hint or "本周",
            "requested_days": fill_plan.get("requested_days", plan.fill_days),
            "fillable_days": fill_plan.get("fillable_days"),
            "total_budget_days": plan.total_person_days,
            "hours_per_day": plan.hours_per_day,
            "conflicts": fill_plan.get("conflicts") or [],
            "entries": fill_plan.get("entries") or [],
            "skipped_days": fill_plan.get("skipped_days") or [],
            "total_hours": fill_plan.get("total_hours"),
        },
    }


def build_execution_summary(plan: WorkpackagePlan, task_id: str, fill_plan: dict) -> str:
    entries = fill_plan.get("entries") or []
    lines = [
        f"已按 **{plan.period_hint or '指定周期'}** 工作日历生成 **{plan.project}** 工时填报：",
        "",
        "一、填报明细",
    ]
    for entry in entries:
        hours = entry.get("hours", plan.hours_per_day)
        lines.append(f"- {entry.get('day_label')}（{entry.get('day_date')}）：{hours:g} 小时")
    total_hours = sum(e.get("hours", plan.hours_per_day) for e in entries)
    lines.extend(
        [
            f"- 合计：**{total_hours:g} 小时**",
            "",
            "二、后续步骤",
            "- 已生成工包填报表单，请在任务卡片中查看并确认提交",
            "",
            "请点击下方任务卡片查看详情。",
        ]
    )
    return "\n".join(lines)


def build_task_metadata(plan: WorkpackagePlan, task_id: str) -> dict:
    return {
        "task_id": task_id,
        "task_title": f"{plan.project or '工包'}填报",
        "progress": "1/2",
        "progress_percent": 50,
        "steps_desc": "工包填报 · 用户确认",
    }
