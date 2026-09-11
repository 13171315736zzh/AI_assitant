"""会议预约流程：槽位收集、会议室冲突与推荐。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta

from pycore.core import get_logger
from pycore.integrations.llm.base import Message

from src.agent.session_context import is_plan_revision_text, merge_user_texts
from src.integrations.llm_factory import create_llm_provider

logger = get_logger()

_MEETING_INTENT = re.compile(r"会议|会议室|预约|预订|订会议|约.{0,12}会议|约.{0,8}会|帮我约")
_ROOM_PATTERN = re.compile(r"(\d{3})\s*会议室|会议室\s*(\d{3})")
_FLEXIBLE_ROOM = re.compile(
    r"哪个会议室都行|哪个都行|任意会议室|会议室.{0,8}(?:都行|都可以|随意|随便)|"
    r"随便.{0,6}会议室|有.{0,4}投屏.{0,6}就行|有.{0,4}投影.{0,6}就行"
)
_EQUIPMENT_PREF = re.compile(r"投屏|投影")
_GN_MEETING = re.compile(
    r"国能会|国能会议|线上会议|视频会议|线上会|线上\s*会|线上.{0,8}会"
)
_ONLINE_MEETING_HINT = re.compile(r"线上会|线上\s*会|线上会议|视频会议|国能会|国能会议")
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
    has_gn_kw = bool(_GN_MEETING.search(text) or _ONLINE_MEETING_HINT.search(text))
    has_online = bool(re.search(r"线上", text))
    has_offline = bool(re.search(r"线下|会议室|哪个会议室|投屏|投影", text))
    has_room_kw = bool(_ROOM_PATTERN.search(text) or has_offline)
    has_book_kw = bool(
        re.search(r"预约|预订|订.{0,4}会议|约.{0,12}会议|约.{0,8}会|帮我约", text)
    )
    has_function = bool(re.search(r"功能会议", text))
    has_meeting_ctx = bool(re.search(r"会|会议", text))

    needs_gn = has_gn_kw or (has_function and not has_room_kw)
    needs_room = has_room_kw or (has_book_kw and not needs_gn)

    # 用户提到「线上会」或「线上」+ 会议语境 → 国能会议预约
    if _ONLINE_MEETING_HINT.search(text) or (has_online and has_meeting_ctx):
        needs_gn = True
    if has_online and has_offline:
        needs_gn = True
        needs_room = True
    elif has_gn_kw and (has_room_kw or _ROOM_PATTERN.search(text)):
        needs_gn = True
        needs_room = True
    if re.search(r"推迟|延期|改到|延后", text) and has_meeting_ctx:
        needs_room = True

    return needs_gn, needs_room


def meeting_plan_mode(plan: MeetingPlan) -> str:
    if plan.needs_gn_meeting and plan.needs_room_booking:
        return "combined"
    if plan.needs_gn_meeting:
        return "gn_only"
    return "room_only"


def _workflow_node_open(wf_plan: dict | None, node_id: str) -> bool:
    if not wf_plan:
        return False
    nodes = wf_plan.get("nodes")
    if not isinstance(nodes, list):
        return False
    for node in nodes:
        if isinstance(node, dict) and node.get("id") == node_id:
            if node.get("status") in ("completed", "cancelled", "submitted"):
                return False
            if node.get("task_id"):
                return False
            return True
    return False


def sync_meeting_plan_with_workflow_nodes(
    plan: MeetingPlan,
    wf_plan: dict | None,
) -> MeetingPlan:
    """将会话办理节点与会议计划模式对齐（国能会 / 会议室可并存）。"""
    if not wf_plan:
        return plan
    if _workflow_node_open(wf_plan, "gn_meeting"):
        plan.needs_gn_meeting = True
    if _workflow_node_open(wf_plan, "room"):
        plan.needs_room_booking = True
    return plan


def resolve_meeting_focus_node(
    wf_plan: dict | None,
    *,
    activated_node: str | None = None,
) -> str | None:
    """确定当前应展示的会议确认卡类型（与右侧办理节点 active_node_id 一致）。"""
    if wf_plan:
        active = wf_plan.get("active_node_id")
        if active in ("gn_meeting", "room") and _workflow_node_open(wf_plan, active):
            return active
    if activated_node in ("gn_meeting", "room"):
        return activated_node
    return None


def meeting_plan_for_node(plan: MeetingPlan, node_id: str | None) -> MeetingPlan:
    """按当前办理节点调整会议计划展示模式（国能会 / 会议室分步确认）。"""
    from copy import copy

    adjusted = copy(plan)
    if node_id == "gn_meeting":
        adjusted.needs_gn_meeting = True
        adjusted.needs_room_booking = False
    elif node_id == "room":
        adjusted.needs_room_booking = True
        adjusted.needs_gn_meeting = False
    return adjusted


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
    if re.search(r"推迟|延期|改到|延后", text) and re.search(r"会议|开会", text):
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


_WEEKDAY_INDEX = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
_CN_DIGIT = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
_POSTPONE_MARKERS = ("推迟到", "延后到", "延期到", "改到", "改为", "调整到", "换到", "移到")

MEETING_SCHEDULE_EXTRACT_SYSTEM = """你是会议预约信息提取助手。根据用户描述提取**改期后/即将举办**的会议安排。

参考日期：{reference_label}（星期{weekday_cn}，ISO {reference_iso})

规则：
1. 用户改期（如「将今天的会议推迟到下周一上午十点」）时，提取改期后的目标日期与时间，不要填原会议日期
2. 「今天」「今日」若仅描述原会议，不要当作目标 meeting_date
3. meeting_date 用 YYYY-MM-DD；start_time/end_time 用 24 小时制 HH:MM
4. 未给出结束时间时 end_time 为 null（系统默认 +1 小时）
5. subject 为会议主题；可从项目名推断（如「神东项目会议」）
6. 只输出 JSON，不要 markdown：
{{"subject":"...","meeting_date":"YYYY-MM-DD","start_time":"HH:MM","end_time":"HH:MM或null","attendees":null或"..."}}"""


def _weekday_cn(d: date) -> str:
    return "一二三四五六日"[d.weekday()]


def _postpone_focus_text(combined: str) -> str:
    text = combined or ""
    for marker in _POSTPONE_MARKERS:
        match = re.search(marker + r"(.+)", text)
        if match:
            return match.group(1).strip("，,。 ")
    return text


def _extract_weekday_hint(text: str) -> str | None:
    match = re.search(r"下(?:周|星期)([一二三四五六日天])", text)
    if match:
        return f"下周{match.group(1)}"
    match = re.search(r"(?:本|这)(?:周|星期)([一二三四五六日天])", text)
    if match:
        return f"本周{match.group(1)}"
    return None


def _resolve_weekday_date(hint: str, today: date) -> date | None:
    hint = (hint or "").strip()
    match = re.search(r"下(?:周|星期)([一二三四五六日天])", hint)
    if match:
        target = _WEEKDAY_INDEX[match.group(1)]
        delta = (target - today.weekday() + 7) % 7 or 7
        return today + timedelta(days=delta)
    match = re.search(r"(?:本|这)(?:周|星期)([一二三四五六日天])", hint)
    if match:
        target = _WEEKDAY_INDEX[match.group(1)]
        delta = (target - today.weekday()) % 7
        return today + timedelta(days=delta)
    if "周四" in hint or "星期四" in hint:
        delta = (3 - today.weekday()) % 7 or 7
        return today + timedelta(days=delta)
    return None


def _chinese_numeral_to_int(text: str) -> int | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    if raw == "十":
        return 10
    if raw.startswith("十"):
        tail = raw[1:]
        return 10 + (_CN_DIGIT.get(tail, 0) if tail else 0)
    if "十" in raw:
        head, tail = raw.split("十", 1)
        tens = _CN_DIGIT.get(head, 1) if head else 1
        ones = _CN_DIGIT.get(tail, 0) if tail else 0
        return tens * 10 + ones
    if raw in _CN_DIGIT:
        return _CN_DIGIT[raw]
    return None


def _parse_chinese_clock(
    combined: str,
    *,
    is_morning: bool,
    is_afternoon: bool,
    is_evening: bool,
) -> tuple[str | None, str | None]:
    match = re.search(
        r"([零〇一二三四五六七八九十两]+)\s*点(?:\s*([零〇一二三四五六七八九十两]+)\s*分)?",
        combined,
    )
    if not match:
        return None, None
    hour = _chinese_numeral_to_int(match.group(1))
    minute = _chinese_numeral_to_int(match.group(2) or "") or 0
    if hour is None:
        return None, None
    if is_evening:
        hour = _parse_evening_hour(hour)
    elif is_afternoon and hour < 12:
        hour += 12
    elif is_morning and hour == 12:
        hour = 0
    start = _normalize_time(hour, minute)
    return start, _add_one_hour(start)


def _parse_meeting_schedule_segment(combined: str) -> tuple[str | None, str | None, str | None]:
    date_hint = _extract_weekday_hint(combined)
    if not date_hint:
        if re.search(r"今晚|今天晚上|今儿晚", combined):
            date_hint = "今天"
        elif re.search(r"明天", combined):
            date_hint = "明天"
        elif re.search(r"后天", combined):
            date_hint = "后天"
        elif re.search(r"今天|今日", combined):
            date_hint = "今天"
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

    cn_start, cn_end = _parse_chinese_clock(
        combined,
        is_morning=is_morning,
        is_afternoon=is_afternoon,
        is_evening=is_evening,
    )
    if cn_start:
        return date_hint, cn_start, cn_end

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


def _parse_meeting_schedule(combined: str) -> tuple[str | None, str | None, str | None]:
    focus = _postpone_focus_text(combined)
    primary = _parse_meeting_schedule_segment(focus)
    if primary[1] or _extract_weekday_hint(focus):
        return primary
    if focus != combined:
        return _parse_meeting_schedule_segment(combined)
    return primary


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
        else:
            resolved = _resolve_weekday_date(plan.date_hint, today)
            if resolved:
                meeting_date = resolved

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
        if not plan.room_preference:
            plan.room_preference = "需要投屏"
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
            postponed_subject = re.search(
                r"(?:的|将)(?:今天|今日|明天|后天)?的?"
                r"([\u4e00-\u9fffA-Za-z0-9]{2,12}(?:项目)?)会议",
                combined,
            )
            if postponed_subject:
                plan.subject = f"{postponed_subject.group(1)}会议"
            if not plan.subject:
                for named in re.finditer(r"([\u4e00-\u9fffA-Za-z0-9]{2,16}?)会议", combined):
                    raw = named.group(1).strip("，, 一个")
                    if raw in ("今天", "今日", "明天", "后天", "这次", "本次", "线上", "线下"):
                        continue
                    if re.search(r"今天|今日|明天|后天", raw):
                        continue
                    plan.subject = raw if raw.endswith("会") else f"{raw}会议"
                    break
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


def build_meeting_plan_confirm_items(
    plan: MeetingPlan,
    *,
    confirm_node_id: str | None = None,
) -> list[dict[str, str]]:
    mode = meeting_plan_mode(plan)
    if confirm_node_id == "gn_meeting":
        mode = "gn_only"
    elif confirm_node_id == "room":
        mode = "room_only"
    subject = plan.subject or "工作会议"
    items = [
        {"label": "会议主题", "value": subject},
    ]
    if mode == "gn_only":
        items.append({"label": "会议形式", "value": "国能会议（线上）"})
    if mode in ("room_only", "combined") and plan.needs_room_booking:
        items.append({"label": "会议室", "value": _room_display(plan)})
        if plan.room_preference:
            items.append({"label": "会议室偏好", "value": plan.room_preference})
    items.extend(
        [
            {"label": "时间", "value": _time_display(plan)},
            {"label": "参会人员", "value": plan.attendees or "待定"},
        ]
    )
    if plan.min_capacity and mode in ("room_only", "combined"):
        items.append({"label": "人数要求", "value": f"{plan.min_capacity} 人以上"})
    return items


def build_meeting_plan_confirm_content(plan: MeetingPlan, *, updated: bool = False) -> str:
    mode = meeting_plan_mode(plan)
    intro = (
        "已根据您补充的信息更新，请在下方卡片中直接修改后确认："
        if updated
        else "会议信息已从对话中识别，请在下方卡片中核对并修改："
    )
    lines = [intro]
    if mode == "gn_only":
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


def build_meeting_plan_confirm_metadata(
    plan: MeetingPlan,
    *,
    confirm_node_id: str | None = None,
) -> dict:
    from src.integrations.mock_meeting_provider import list_room_presets

    mode = meeting_plan_mode(plan)
    if confirm_node_id == "gn_meeting":
        mode = "gn_only"
    elif confirm_node_id == "room":
        mode = "room_only"
    elif confirm_node_id is None and mode == "combined":
        confirm_node_id = "gn_meeting"
        mode = "gn_only"

    confirm_label = "确认开始办理"
    if mode == "gn_only":
        confirm_label = "确认并开始国能会议预约"
    elif mode == "room_only":
        confirm_label = "确认并开始会议室预约" if not plan.room_flexible else "确认并选择会议室"

    schedule = resolve_meeting_datetime(plan)
    start = _time_input_hint(plan.start_hint, "14:00")
    end = _time_input_hint(plan.end_hint, _add_one_hour(start))

    if mode == "gn_only":
        title = f"{plan.subject or '国能会议'}预约"
    elif mode == "room_only":
        title = f"{plan.subject or '会议'}会议室预约"
    else:
        title = f"{plan.subject or '会议'}预约"

    subject = plan.subject or "工作会议"
    room_display = ""
    if plan.room:
        room_display = (
            f"{plan.room} 会议室" if str(plan.room).isdigit() else str(plan.room)
        )

    meta: dict = {
        "status": "pending",
        "title": title,
        "items": build_meeting_plan_confirm_items(plan, confirm_node_id=confirm_node_id),
        "confirm_label": confirm_label,
        "plan_mode": mode,
        "confirm_node_id": confirm_node_id,
        "needs_gn_meeting": mode == "gn_only",
        "needs_room_booking": mode == "room_only",
        "subject": subject,
        "meeting_name": subject,
        "meeting_topic": subject,
        "selected_room": plan.room,
        "room_display": room_display,
        "room_flexible": plan.room_flexible,
        "attendees": plan.attendees or "",
        "attendees_hint": "填写参会人姓名、邮箱或国能工号，多人用顿号/逗号分隔",
        "date_hint": schedule["meeting_date"],
        "start_hint": start,
        "end_hint": end,
    }
    if mode == "room_only":
        presets = list_room_presets()
        if plan.min_capacity:
            presets = [room for room in presets if int(room.get("capacity") or 0) >= plan.min_capacity]
        meta["room_options"] = presets
        meta["room_preference"] = plan.room_preference or plan.equipment_pref or ""
        meta["room_preference_hint"] = "如投屏、20 人以上、靠近电梯等"
        if plan.min_capacity:
            meta["min_capacity"] = plan.min_capacity
    return {
        "interactive": True,
        "meeting_plan_confirm": meta,
    }


def _parse_schedule_extract_json(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None


def _apply_schedule_extract(plan: MeetingPlan, data: dict) -> None:
    subject = str(data.get("subject") or "").strip()
    if subject:
        plan.subject = subject

    meeting_date = str(data.get("meeting_date") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", meeting_date):
        plan.date_hint = meeting_date

    start_time = str(data.get("start_time") or "").strip()
    if re.match(r"\d{1,2}:\d{2}", start_time):
        plan.start_hint = _time_input_hint(start_time, start_time)

    end_time = data.get("end_time")
    if end_time and re.match(r"\d{1,2}:\d{2}", str(end_time).strip()):
        plan.end_hint = _time_input_hint(str(end_time).strip(), str(end_time).strip())
    elif plan.start_hint:
        plan.end_hint = _add_one_hour(plan.start_hint)

    attendees = data.get("attendees")
    if attendees:
        plan.attendees = str(attendees).strip()


async def enrich_meeting_plan_schedule(
    plan: MeetingPlan,
    user_text: str,
    *,
    today: date | None = None,
) -> MeetingPlan:
    """用 LLM 理解改期/相对日期后的会议时间；失败时回退到规则解析。"""
    text = (user_text or plan.raw_goal or "").strip()
    if not text:
        return plan
    if _has_schedule(plan):
        return plan

    today = today or date.today()
    system = MEETING_SCHEDULE_EXTRACT_SYSTEM.format(
        reference_label=today.strftime("%Y年%m月%d日"),
        weekday_cn=_weekday_cn(today),
        reference_iso=today.isoformat(),
    )
    try:
        provider = create_llm_provider()
        response = await provider.chat(
            [Message.system(system), Message.user(text)],
            temperature=0.1,
            max_tokens=280,
        )
        extracted = _parse_schedule_extract_json(response.content or "")
        if extracted and (extracted.get("meeting_date") or extracted.get("start_time")):
            _apply_schedule_extract(plan, extracted)
            return plan
    except Exception as exc:
        logger.warning("Meeting schedule LLM extract failed", error=str(exc))

    focus = _postpone_focus_text(text)
    parsed_date, parsed_start, parsed_end = _parse_meeting_schedule(focus)
    if parsed_date:
        plan.date_hint = parsed_date
    if parsed_start:
        plan.start_hint = parsed_start
    if parsed_end:
        plan.end_hint = parsed_end
    return plan


def apply_meeting_plan_draft(plan: MeetingPlan, draft: dict | None) -> MeetingPlan:
    """合并确认卡片上的点选/填写内容；与对话或输入框解析冲突时，以卡片非空字段为准。"""
    if not draft:
        return plan

    topic = str(draft.get("meeting_topic") or "").strip()
    name = str(draft.get("meeting_name") or "").strip()
    subject = str(draft.get("subject") or "").strip()
    resolved = topic or name or subject
    if resolved:
        plan.subject = resolved

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
    elif room_raw:
        plan.room = room_raw
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
    return (
        f"「{plan.subject or '国能会议'}」信息已确认。"
        "请点击中间选项卡打开划窗，核对步骤后前往 OA 提交；下方可继续办理下一事项。"
    )


def build_room_execution_summary(
    plan: MeetingPlan, task_id: str, room: str, time_label: str
) -> str:
    return (
        f"「{plan.subject or '会议'}」会议室信息已确认。"
        "请点击中间选项卡打开划窗，核对步骤后前往 OA 提交；下方可继续办理下一事项。"
    )


def build_combined_execution_summary(
    plan: MeetingPlan,
    *,
    room_task_id: str,
    gn_task_id: str,
    room: str,
    time_label: str,
) -> str:
    return (
        "国能会议与会议室信息已确认。"
        "请点击中间选项卡打开划窗，核对步骤后前往 OA 提交；下方可继续办理下一事项。"
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
        "confirmed_items": build_meeting_plan_confirm_items(plan, confirm_node_id="gn_meeting"),
    }


def build_room_task_metadata(plan: MeetingPlan, task_id: str) -> dict:
    return {
        "task_id": task_id,
        "task_title": f"{plan.subject or '会议'}会议室预约",
        "progress": "1/3",
        "progress_percent": 33,
        "steps_desc": "会议室确认 · 会议预约 · 用户确认",
        "meeting_kind": "room",
        "confirmed_items": build_meeting_plan_confirm_items(plan, confirm_node_id="room"),
    }


def build_task_metadata(plan: MeetingPlan, task_id: str) -> dict:
    if plan.needs_gn_meeting and not plan.needs_room_booking:
        return build_gn_task_metadata(plan, task_id)
    return build_room_task_metadata(plan, task_id)
