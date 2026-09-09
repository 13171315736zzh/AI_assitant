"""会议预约流程：槽位收集、会议室冲突与推荐。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from src.agent.session_context import is_plan_revision_text, merge_user_texts

_MEETING_INTENT = re.compile(r"会议|会议室|预约|预订|订会议|约.{0,12}会议|约.{0,8}会|帮我约")
_ROOM_PATTERN = re.compile(r"(\d{3})\s*会议室|会议室\s*(\d{3})")
_FLEXIBLE_ROOM = re.compile(
    r"哪个会议室都行|哪个都行|任意会议室|会议室.{0,8}(?:都行|都可以|随意|随便)|"
    r"随便.{0,6}会议室|有.{0,4}投屏.{0,6}就行|有.{0,4}投影.{0,6}就行"
)
_EQUIPMENT_PREF = re.compile(r"投屏|投影")
_GN_MEETING = re.compile(r"国能会|线上会议|视频会议")
_CAPACITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(\d+)\s*人\s*以上"),
    re.compile(r"至少\s*(\d+)\s*人"),
    re.compile(r"(\d+)\s*人以上的?(?:会议)?室"),
    re.compile(r"容纳\s*(\d+)\s*人"),
    re.compile(r"需要\s*(\d+)\s*人"),
    re.compile(r"(\d+)\s*人(?:左右|规模)?(?:的?(?:会议|会议室))?"),
)


def _parse_room_code(text: str) -> str | None:
    """从「236」「236会议室」等文本提取三位会议室号。"""
    raw = (text or "").strip()
    if not raw:
        return None
    room_match = _ROOM_PATTERN.search(raw)
    if room_match:
        return room_match.group(1) or room_match.group(2)
    digits = re.sub(r"[^\d]", "", raw)
    if len(digits) == 3:
        return digits
    if raw:
        return raw
    return None


@dataclass
class MeetingPlan:
    subject: str | None = None
    room: str | None = None
    room_flexible: bool = False
    room_preference: str | None = None
    equipment_pref: str | None = None
    date_hint: str | None = None
    start_hint: str | None = None
    end_hint: str | None = None
    attendees: str | None = None
    min_capacity: int | None = None
    raw_goal: str = ""
    needs_gn_meeting: bool = False
    needs_room_booking: bool = False


def detect_meeting_modes(combined: str) -> tuple[bool, bool]:
    """区分国能会（线上）与线下会议室预约，二者可独立或同时进行。"""
    text = combined or ""
    has_gn_kw = bool(_GN_MEETING.search(text))
    has_room_kw = bool(
        _ROOM_PATTERN.search(text)
        or re.search(r"会议室|线下|哪个会议室|投屏|投影", text)
    )
    has_book_kw = bool(
        re.search(r"预约|预订|订.{0,4}会议|约.{0,12}会议|约.{0,8}会|帮我约", text)
    )
    has_function = bool(re.search(r"功能会议", text))

    needs_gn = has_gn_kw or (has_function and not has_room_kw)
    needs_room = has_room_kw or (has_book_kw and not needs_gn)

    if has_gn_kw and (has_room_kw or _ROOM_PATTERN.search(text)):
        needs_gn = True
        needs_room = True

    return needs_gn, needs_room


def meeting_plan_mode(plan: MeetingPlan) -> str:
    if plan.needs_gn_meeting and plan.needs_room_booking:
        return "combined"
    if plan.needs_gn_meeting:
        return "gn_only"
    return "room_only"


def is_gn_meeting_plan(plan: MeetingPlan) -> bool:
    return plan.needs_gn_meeting


def _meeting_intent_on_text(text: str) -> bool:
    needs_gn, needs_room = detect_meeting_modes(text)
    if needs_gn or needs_room:
        return True
    if not _MEETING_INTENT.search(text):
        return False
    if re.search(
        r"预约|预订|订.*会议|约.{0,12}会议|约.{0,8}会|帮我约|会议室|开会|定.*会议",
        text,
    ):
        return True
    return bool(_ROOM_PATTERN.search(text))


def is_meeting_workflow_intent_current(text: str) -> bool:
    """仅根据当前这一轮用户发言判断会议意图（已完成会话中的新诉求）。"""
    from src.agent.travel_workflow import is_transport_or_travel_booking_intent

    latest = (text or "").strip()
    if not latest:
        return False
    if is_transport_or_travel_booking_intent(latest):
        return False
    return _meeting_intent_on_text(latest)


def is_meeting_workflow_intent(text: str) -> bool:
    return _meeting_intent_on_text(text)


def _normalize_time(hour: int, minute: int = 0) -> str:
    return f"{hour:02d}:{minute:02d}"


def _time_input_hint(value: str | None, fallback: str) -> str:
    raw = (value or fallback).strip()
    match = re.match(r"^(\d{1,2}):(\d{2})", raw)
    if not match:
        return fallback
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def _add_one_hour(start: str) -> str:
    hour, minute = [int(part) for part in start.split(":", 1)]
    end_hour = hour + 1
    if end_hour >= 24:
        end_hour = 23
        minute = 59
    return _normalize_time(end_hour, minute)


def _parse_evening_hour(hour: int) -> int:
    if 1 <= hour <= 11:
        return hour + 12
    return hour


def _parse_meeting_schedule(combined: str) -> tuple[str | None, str | None, str | None]:
    date_hint: str | None = None
    if re.search(r"今晚|今天晚上|今儿晚", combined):
        date_hint = "今天"
    elif re.search(r"今天|今日", combined):
        date_hint = "今天"
    elif re.search(r"明天", combined):
        date_hint = "明天"
    elif re.search(r"后天", combined):
        date_hint = "后天"
    elif re.search(r"本周四|星期四|周四", combined):
        date_hint = "本周四"

    is_evening = bool(re.search(r"今晚|晚上|夜间|今儿晚", combined))
    is_afternoon = "下午" in combined
    is_morning = "上午" in combined and not is_afternoon

    time_range = re.search(
        r"(\d{1,2})\s*[点:：]\s*(\d{0,2})?\s*[到至\-~]\s*(\d{1,2})\s*[点:：]?",
        combined,
    )
    if time_range:
        sh = int(time_range.group(1))
        sm = int(time_range.group(2) or 0)
        eh = int(time_range.group(3))
        if is_afternoon and sh < 12:
            sh += 12
        if is_afternoon and eh < 12:
            eh += 12
        if is_evening:
            sh = _parse_evening_hour(sh)
            eh = _parse_evening_hour(eh)
        return date_hint, _normalize_time(sh, sm), _normalize_time(eh)

    tonight = re.search(r"今晚\s*(\d{1,2})\s*点(?:\s*(\d{1,2}))?", combined)
    if tonight:
        hour = _parse_evening_hour(int(tonight.group(1)))
        minute = int(tonight.group(2) or 0)
        start = _normalize_time(hour, minute)
        return date_hint or "今天", start, _add_one_hour(start)

    evening_point = re.search(r"(?:晚上|夜间)\s*(\d{1,2})\s*点(?:\s*(\d{1,2}))?", combined)
    if evening_point:
        hour = _parse_evening_hour(int(evening_point.group(1)))
        minute = int(evening_point.group(2) or 0)
        start = _normalize_time(hour, minute)
        return date_hint, start, _add_one_hour(start)

    clock = re.search(r"(\d{1,2})\s*[点:：](\d{0,2})?", combined)
    if clock and not re.search(r"[到至\-~]", combined):
        hour = int(clock.group(1))
        minute = int(clock.group(2) or 0)
        if is_evening:
            hour = _parse_evening_hour(hour)
        elif is_afternoon and hour < 12:
            hour += 12
        elif is_morning and hour == 12:
            hour = 0
        start = _normalize_time(hour, minute)
        return date_hint, start, _add_one_hour(start)

    if is_afternoon:
        return date_hint, "14:00", "15:00"
    if is_morning:
        return date_hint, "09:00", "10:00"
    if re.search(r"2\s*点\s*到\s*4\s*点|14\s*[点:]\s*到\s*16", combined):
        return date_hint, "14:00", "16:00"
    return date_hint, None, None


def resolve_meeting_datetime(
    plan: MeetingPlan,
    *,
    today: date | None = None,
) -> dict[str, str]:
    today = today or date.today()
    meeting_date = today
    if plan.date_hint:
        iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", plan.date_hint.strip())
        if iso_match:
            meeting_date = date(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3)),
            )
        elif "今天" in plan.date_hint or "今晚" in plan.date_hint:
            meeting_date = today
        elif "明天" in plan.date_hint:
            meeting_date = today + timedelta(days=1)
        elif "后天" in plan.date_hint:
            meeting_date = today + timedelta(days=2)
        elif "周四" in plan.date_hint:
            weekday = today.weekday()
            delta = (3 - weekday) % 7 or 7
            meeting_date = today + timedelta(days=delta)

    start = plan.start_hint or "14:00"
    end = plan.end_hint or _add_one_hour(start)
    if len(start) == 5:
        start = f"{start}:00"
    if len(end) == 5:
        end = f"{end}:00"

    time_label = f"{meeting_date.isoformat()} {start[:5]}-{end[:5]}"
    return {
        "meeting_date": meeting_date.isoformat(),
        "start_time": f"{meeting_date.isoformat()} {start}",
        "end_time": f"{meeting_date.isoformat()} {end}",
        "time_label": time_label,
    }


def _parse_min_capacity(combined: str) -> int | None:
    """从「20人以上」「至少20人」等表述提取最低容纳人数。"""
    values: list[int] = []
    for pattern in _CAPACITY_PATTERNS:
        for match in pattern.finditer(combined):
            try:
                values.append(int(match.group(1)))
            except (TypeError, ValueError):
                continue
    return max(values) if values else None


def build_meeting_plan(messages) -> MeetingPlan:
    combined = merge_user_texts(
        [
            record.content.strip()
            for record in messages
            if getattr(record, "role", None) == "user" and record.content.strip()
        ]
    )
    plan = MeetingPlan(raw_goal=combined[:200])
    plan.needs_gn_meeting, plan.needs_room_booking = detect_meeting_modes(combined)

    room_match = _ROOM_PATTERN.search(combined)
    if room_match:
        plan.room = room_match.group(1) or room_match.group(2)
        plan.room_flexible = False

    if _FLEXIBLE_ROOM.search(combined):
        plan.room_flexible = True
        plan.room = None
    if _EQUIPMENT_PREF.search(combined):
        plan.equipment_pref = "投影"
        if not plan.room:
            plan.room_flexible = True

    parsed_date, parsed_start, parsed_end = _parse_meeting_schedule(combined)
    if parsed_date:
        plan.date_hint = parsed_date
    if parsed_start:
        plan.start_hint = parsed_start
    if parsed_end:
        plan.end_hint = parsed_end

    # 已明确时段但未指定具体会议室 → 走灵活选室（仅线下预约需要）
    if plan.needs_room_booking and not plan.room and not plan.room_flexible and plan.start_hint:
        plan.room_flexible = True

    if "进度" in combined:
        plan.subject = "项目进度会"
    elif "评审" in combined:
        plan.subject = "项目评审会"
    else:
        subject_match = re.search(r"开(.{2,12}?)(?:会议|会)[。！？?]*$", combined)
        if subject_match:
            plan.subject = subject_match.group(1).strip("，, ")
        if not plan.subject:
            typed = re.search(r"的([\u4e00-\u9fff]{2,8}?)会议", combined)
            if typed:
                raw = typed.group(1).strip("，, ")
            else:
                tail = re.search(r"([\u4e00-\u9fff]{2,8}?)会议", combined)
                raw = tail.group(1).strip("，, 一个") if tail else ""
            if raw and not re.search(r"点|今晚|今天|明天|后天", raw):
                plan.subject = raw if raw.endswith("会") else f"{raw}会议"
    if not plan.subject:
        plan.subject = "工作会议"

    attendees = re.search(r"参会[人员]*[:：]?\s*([\u4e00-\u9fff、,，\s]{2,30})", combined)
    if attendees:
        plan.attendees = attendees.group(1).strip()

    capacity = _parse_min_capacity(combined)
    if capacity:
        plan.min_capacity = capacity

    _apply_default_schedule(plan, combined)
    return plan


def _apply_default_schedule(plan: MeetingPlan, combined: str) -> None:
    """用户未说清时段时给出可核对的默认推断，避免让用户做填空题。"""
    if plan.start_hint:
        if not plan.date_hint:
            plan.date_hint = "今天"
        return

    if re.search(r"后天", combined):
        plan.date_hint = "后天"
    elif re.search(r"明天", combined):
        plan.date_hint = "明天"
    else:
        plan.date_hint = plan.date_hint or "今天"

    if re.search(r"上午", combined):
        plan.start_hint = "09:00"
    elif re.search(r"下午", combined):
        plan.start_hint = "14:00"
    elif re.search(r"晚上|今晚", combined):
        plan.start_hint = "19:00"
    else:
        plan.start_hint = "14:00"

    plan.end_hint = _add_one_hour(plan.start_hint)


def _has_schedule(plan: MeetingPlan) -> bool:
    return bool(plan.start_hint)


def has_meeting_schedule(plan: MeetingPlan) -> bool:
    return _has_schedule(plan)


def can_present_meeting_confirm(plan: MeetingPlan) -> bool:
    """信息足够展示核对卡片（判断题），而非让用户填空。"""
    return bool(plan.subject and _has_schedule(plan))


def build_time_adjustment_phrase(option: dict[str, str]) -> str:
    """将卡片中选中的时段转为自然语言，供确认时合并进对话上下文。"""
    date_hint = str(option.get("date_hint") or "今天")
    start = str(option.get("start_hint") or "14:00")
    hour = int(start.split(":", 1)[0])
    if date_hint == "今天" and hour >= 18:
        return f"今晚{hour}点"
    if date_hint == "今天":
        period = "上午" if hour < 12 else "下午"
        return f"今天{period}{hour}点"
    if date_hint == "明天":
        period = "上午" if hour < 12 else "下午"
        return f"明天{period}{hour}点"
    return f"{date_hint}{hour}点"


def build_meeting_time_options(plan: MeetingPlan) -> list[dict[str, str | bool]]:
    """相邻时段备选项，供用户在卡片中点选（选择题）。"""
    if not plan.start_hint:
        return []

    hour = int(plan.start_hint.split(":", 1)[0])
    base_date = plan.date_hint or "今天"
    options: list[dict[str, str | bool]] = []
    for delta in (-1, 0, 1):
        slot_hour = hour + delta
        if slot_hour < 8 or slot_hour > 21:
            continue
        start = _normalize_time(slot_hour, 0)
        end = _add_one_hour(start)
        temp = MeetingPlan(
            date_hint=base_date,
            start_hint=start,
            end_hint=end,
        )
        label = resolve_meeting_datetime(temp)["time_label"]
        options.append(
            {
                "label": label,
                "date_hint": base_date,
                "start_hint": start,
                "end_hint": end,
                "selected": start == plan.start_hint,
            }
        )

    if options and not any(bool(item.get("selected")) for item in options):
        mid = len(options) // 2
        options[mid]["selected"] = True
    return options


def missing_slots(plan: MeetingPlan) -> list[str]:
    missing: list[str] = []
    if not plan.needs_gn_meeting and not plan.needs_room_booking:
        missing.append("会议类型")
    if plan.needs_room_booking and not plan.room and not plan.room_flexible:
        missing.append("会议室")
    if not _has_schedule(plan):
        missing.append("会议日期或时段")
    return missing


def is_ready_to_execute(plan: MeetingPlan) -> bool:
    return (
        (plan.needs_gn_meeting or plan.needs_room_booking)
        and len(missing_slots(plan)) == 0
    )


def _plan_item(label: str, value: str | None) -> dict[str, str]:
    return {"label": label, "value": value.strip() if value else "—"}


def _room_display(plan: MeetingPlan) -> str:
    if plan.needs_gn_meeting and not plan.needs_room_booking:
        return "国能会议（线上）"
    if plan.room:
        return f"{plan.room} 会议室"
    if plan.room_flexible:
        pref = f"（{plan.equipment_pref}）" if plan.equipment_pref else ""
        return f"输入其它{pref}"
    return "点选或双击填写"


def _time_display(plan: MeetingPlan) -> str:
    schedule = resolve_meeting_datetime(plan)
    return schedule["time_label"]


def meeting_plan_confirm_items(plan: MeetingPlan) -> list[dict[str, str]]:
    items = [
        _plan_item("会议名称", plan.subject or "工作会议"),
        _plan_item("会议室", _room_display(plan)),
        _plan_item("会议时间", _time_display(plan)),
    ]
    if plan.attendees:
        items.append(_plan_item("参会人员", plan.attendees))
    if plan.min_capacity:
        items.append(_plan_item("人数要求", f"{plan.min_capacity} 人以上"))
    return items


_ROOM_CANCEL = re.compile(r"取消|退订|撤销|作废|不要(?:了)?")
_ROOM_CANCEL_TARGET = re.compile(
    r"会议室|会议预约|会议预定|线下会议|room\s*\d+|403|236|235|240",
    re.I,
)


def is_room_cancel_intent(text: str) -> bool:
    """取消已预约/进行中的线下会议室（不应打开差旅或会议确认卡）。"""
    stripped = (text or "").strip()
    if not stripped or not _ROOM_CANCEL.search(stripped):
        return False
    return bool(_ROOM_CANCEL_TARGET.search(stripped))


def build_room_cancel_confirm_content() -> str:
    return "请确认是否取消以下会议室预约："


def build_room_cancel_confirm_metadata(snapshot: dict[str, str], task_id: str) -> dict:
    return {
        "interactive": True,
        "room_cancel_confirm": {
            "status": "pending",
            "title": "确认取消会议室",
            "confirm_label": "确认取消",
            "task_id": task_id,
            **snapshot,
        },
    }


def is_meeting_plan_update(text: str) -> bool:
    """待确认会议单存在时，识别用户的补充/修正说明。"""
    if is_room_cancel_intent(text):
        return False
    if is_plan_revision_text(text):
        return True
    if re.search(r"会议室|会议时间|会议名称|参会|主题|投屏|投影", text):
        return True
    if _MEETING_INTENT.search(text):
        return True
    if _ROOM_PATTERN.search(text):
        return True
    if re.search(
        r"明天|后天|今天|今晚|周[一二三四五六日]|上午|下午|\d+\s*[点:：]|进度|评审|参会|投屏|投影|\d+\s*人",
        text,
    ):
        return True
    return False


def build_meeting_plan_confirm_items(plan: MeetingPlan) -> list[dict[str, str]]:
    items = [
        {"label": "会议名称", "value": plan.subject or "工作会议"},
    ]
    if plan.needs_room_booking:
        items.append({"label": "会议室", "value": _room_display(plan)})
        if plan.room_preference:
            items.append({"label": "会议室偏好", "value": plan.room_preference})
    elif plan.needs_gn_meeting:
        items.append({"label": "会议形式", "value": "国能会议（线上）"})
    items.extend(
        [
            {"label": "时间", "value": _time_display(plan)},
            {"label": "参会人员", "value": plan.attendees or "待定"},
        ]
    )
    if plan.min_capacity:
        items.append({"label": "人数要求", "value": f"{plan.min_capacity} 人以上"})
    return items


def build_meeting_plan_confirm_content(plan: MeetingPlan, *, updated: bool = False) -> str:
    mode = meeting_plan_mode(plan)
    intro = (
        "已根据您补充的信息更新如下理解，请核对："
        if updated
        else "根据您的描述，我理解会议安排如下，请核对："
    )
    lines = [intro, ""]
    for item in build_meeting_plan_confirm_items(plan):
        lines.append(f"- {item['label']}：{item['value']}")
    if mode == "combined":
        lines.extend(
            [
                "",
                "👇 将同时办理国能会议（线上）与线下会议室预约，请在卡片中核对并确认。",
            ]
        )
    elif mode == "gn_only":
        lines.extend(
            [
                "",
                "👇 此为线上国能会议预约，确认后将跳转 OA 页面，核对信息并点击「创建」即可完成。",
            ]
        )
    elif plan.needs_room_booking:
        lines.extend(
            [
                "",
                "若会议时间理解有误，可在下方卡片中直接修改日期与时间；确认后将进入会议室选择。",
            ]
        )
    elif plan.room_flexible:
        lines.extend(
            [
                "",
                "👇 可在下方卡片中点选或填写会议室与参会人员，确认后继续办理。",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "👇 可在下方卡片中核对并修改会议室、参会人员等信息，确认后继续办理。",
            ]
        )
    return "\n".join(lines)


def build_meeting_plan_confirm_metadata(plan: MeetingPlan) -> dict:
    from src.integrations.mock_meeting_provider import list_room_presets

    mode = meeting_plan_mode(plan)
    confirm_label = "确认开始办理"
    if mode == "combined":
        confirm_label = "确认并办理（国能会议 + 会议室）"
    elif mode == "gn_only":
        confirm_label = "确认并开始国能会议预约"
    elif plan.room_flexible:
        confirm_label = "确认并选择会议室"

    schedule = resolve_meeting_datetime(plan)
    start = _time_input_hint(plan.start_hint, "14:00")
    end = _time_input_hint(plan.end_hint, _add_one_hour(start))

    meta: dict = {
        "status": "pending",
        "title": f"{plan.subject or '会议'}预约",
        "items": build_meeting_plan_confirm_items(plan),
        "confirm_label": confirm_label,
        "plan_mode": mode,
        "needs_gn_meeting": plan.needs_gn_meeting,
        "needs_room_booking": plan.needs_room_booking,
        "subject": plan.subject or "工作会议",
        "selected_room": plan.room,
        "room_flexible": plan.room_flexible,
        "attendees": plan.attendees or "",
        "attendees_hint": "填写参会人姓名、邮箱或国能工号，多人用顿号/逗号分隔",
        "date_hint": schedule["meeting_date"],
        "start_hint": start,
        "end_hint": end,
        "time_hint": "可直接修改日期、开始与结束时间",
    }
    if plan.needs_room_booking:
        presets = list_room_presets()
        if plan.min_capacity:
            presets = [room for room in presets if int(room.get("capacity") or 0) >= plan.min_capacity]
        meta["room_options"] = presets
        meta["room_hint"] = (
            f"已按 {plan.min_capacity} 人以上筛选；点选备选会议室，或选择输入其它后填写名称"
            if plan.min_capacity
            else "点选备选会议室，或选择输入其它后填写名称"
        )
        meta["room_preference"] = plan.room_preference or plan.equipment_pref or ""
        meta["room_preference_hint"] = "如投屏、20 人以上、靠近电梯等"
        if plan.min_capacity:
            meta["min_capacity"] = plan.min_capacity
    return {
        "interactive": True,
        "meeting_plan_confirm": meta,
    }


def apply_meeting_plan_draft(plan: MeetingPlan, draft: dict | None) -> MeetingPlan:
    """合并确认卡片上的点选/填写内容；与对话或输入框解析冲突时，以卡片非空字段为准。"""
    if not draft:
        return plan

    subject = str(draft.get("subject") or "").strip()
    if subject:
        plan.subject = subject

    attendees = draft.get("attendees")
    if attendees is not None:
        text = str(attendees).strip()
        plan.attendees = text or None

    if draft.get("room_flexible") is True:
        plan.room_flexible = True
        plan.room = None
    elif draft.get("room_flexible") is False:
        plan.room_flexible = False

    room_raw = str(draft.get("room") or draft.get("selected_room") or "").strip()
    room_code = _parse_room_code(room_raw)
    if room_code:
        plan.room = room_code
        plan.room_flexible = False

    pref = draft.get("room_preference")
    if pref is not None:
        text = str(pref).strip()
        plan.room_preference = text or None
        if text and re.search(r"投屏|投影", text):
            plan.equipment_pref = "投影"

    if draft.get("date_hint"):
        plan.date_hint = str(draft["date_hint"])
    if draft.get("start_hint"):
        plan.start_hint = str(draft["start_hint"])
    if draft.get("end_hint"):
        plan.end_hint = str(draft["end_hint"])

    return plan


def build_room_selection_content(plan: MeetingPlan, availability: dict) -> str:
    room = plan.room or availability.get("requested_room", "")
    time_label = availability.get("time_label", "")
    reason = availability.get("conflict_reason") or ""
    options = availability.get("alternatives") or []
    capacity_line = ""
    if plan.min_capacity:
        capacity_line = f"已按 **{plan.min_capacity} 人以上** 筛选可用会议室。"
    if plan.room_flexible or availability.get("browse_mode"):
        equip = plan.equipment_pref or "投屏"
        lines = [
            f"已查询会议系统 **{time_label}** 时段可用会议室（需 **{equip}**）。",
        ]
        if capacity_line:
            lines.append(capacity_line)
        if not options:
            lines.extend(
                [
                    "",
                    f"当前时段暂无满足 **{plan.min_capacity} 人以上** 要求的会议室，请调整人数或更换时段后重试。",
                ]
            )
            return "\n".join(lines)
        lines.extend(
            [
                "",
                "下方列出符合条件的备选会议室，请直接点选后确认预约。",
            ]
        )
        return "\n".join(lines)

    lines = [
        f"已查询 **{room} 会议室** {time_label} 的预订情况。",
    ]
    if capacity_line:
        lines.append(capacity_line)
    lines.extend(
        [
            "",
            reason,
            "",
            "该时段暂不可用。下方为您推荐了同时段可用的会议室，请选择后确认预约。"
            if options
            else f"该时段暂无满足 **{plan.min_capacity} 人以上** 要求的替代会议室，请调整人数或更换时段。",
        ]
    )
    return "\n".join(lines)


def build_room_selection_metadata(plan: MeetingPlan, availability: dict) -> dict:
    return {
        "interactive": True,
        "room_selection": {
            "status": "pending",
            "subject": plan.subject or "工作会议",
            "requested_room": availability.get("requested_room") or plan.room or "",
            "time_label": availability.get("time_label", ""),
            "start_time": availability.get("start_time", ""),
            "end_time": availability.get("end_time", ""),
            "conflict_reason": availability.get("conflict_reason"),
            "equipment_pref": plan.equipment_pref,
            "min_capacity": plan.min_capacity,
            "browse_mode": bool(plan.room_flexible or availability.get("browse_mode")),
            "options": availability.get("alternatives") or [],
            "needs_gn_meeting": plan.needs_gn_meeting,
            "needs_room_booking": plan.needs_room_booking,
        }
    }


def build_gn_execution_summary(plan: MeetingPlan, task_id: str, time_label: str) -> str:
    return "\n".join(
        [
            f"国能会议信息已确认，已为您启动「{plan.subject or '国能会议'}」办理流程：",
            "",
            "一、会议信息",
            f"- 主题：{plan.subject or '国能会议'}",
            f"- 时间：{time_label}",
            f"- 形式：**国能会议（线上/视频）**",
            "",
            "二、后续步骤",
            "- 请在任务卡片中点击「确认继续」，跳转 OA 核对会议信息",
            "- 点击「创建」后将返回**会议链接**与**会议密码**，支持一键复制",
            "",
            "请点击下方任务卡片查看详情。",
        ]
    )


def build_room_execution_summary(
    plan: MeetingPlan, task_id: str, room: str, time_label: str
) -> str:
    return "\n".join(
        [
            f"会议室已确认，已为您启动「{plan.subject or '会议预约'}」办理流程：",
            "",
            "一、会议信息",
            f"- 主题：{plan.subject or '工作会议'}",
            f"- 时间：{time_label}",
            f"- 会议室：**{room} 会议室**",
            f"- 参会人员：{plan.attendees or '待定'}",
            "",
            "二、后续步骤",
            "- 请在任务卡片中点击「确认继续」，跳转 OA 提交审批",
            "- 审批通过后将展示完整预约信息（会议室、主题、时间、参会人员）",
            "",
            "请点击下方任务卡片查看详情。",
        ]
    )


def build_combined_execution_summary(
    plan: MeetingPlan,
    *,
    room_task_id: str,
    gn_task_id: str,
    room: str,
    time_label: str,
) -> str:
    return "\n".join(
        [
            f"已为您同时启动「{plan.subject or '会议'}」线下预约与国能会议办理：",
            "",
            "一、线下会议室",
            f"- 会议室：**{room} 会议室**",
            f"- 时间：{time_label}",
            "",
            "二、国能会议（线上）",
            f"- 主题：{plan.subject or '国能会议'}",
            f"- 时间：{time_label}",
            "",
            "三、后续步骤",
            "- 下方有两个任务卡片，请分别点击「确认继续」并完成 OA 办理",
            "- 国能会议在 OA 页面点击「创建」即可；线下会议室仍需提交审批",
            "- 国能会议创建成功后将返回会议链接与密码",
            "- 会议室审批通过后将展示完整预约信息",
        ]
    )


def build_execution_summary(plan: MeetingPlan, task_id: str, room: str, time_label: str) -> str:
    if plan.needs_gn_meeting and not plan.needs_room_booking:
        return build_gn_execution_summary(plan, task_id, time_label)
    return build_room_execution_summary(plan, task_id, room, time_label)


def build_gn_task_metadata(plan: MeetingPlan, task_id: str) -> dict:
    return {
        "task_id": task_id,
        "task_title": f"{plan.subject or '国能会议'}预约",
        "progress": "1/2",
        "progress_percent": 50,
        "steps_desc": "国能会议预约 · 用户确认",
        "meeting_kind": "gn",
    }


def build_room_task_metadata(plan: MeetingPlan, task_id: str) -> dict:
    return {
        "task_id": task_id,
        "task_title": f"{plan.subject or '会议'}会议室预约",
        "progress": "1/3",
        "progress_percent": 33,
        "steps_desc": "会议室确认 · 会议预约 · 用户确认",
        "meeting_kind": "room",
    }


def build_task_metadata(plan: MeetingPlan, task_id: str) -> dict:
    if plan.needs_gn_meeting and not plan.needs_room_booking:
        return build_gn_task_metadata(plan, task_id)
    return build_room_task_metadata(plan, task_id)
