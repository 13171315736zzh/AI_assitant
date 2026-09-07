"""差旅办事流程：槽位收集、就绪判定、任务与表单生成。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from src.agent.email_etiquette import infer_salutation
from src.agent.travel_policy_knowledge import accommodation_standard_other, estimate_train_hours
from src.agent.travel_policy_rules import extract_trip_days, parse_travel_context
from src.agent.session_context import is_plan_revision_text, merge_user_texts
from src.agent.user_memory import resolve_travel_staff_level

_TRAVEL_INTENT = re.compile(
    r"出差|差旅|订票|机票|酒店|行程|办公地点|驻场|"
    r"住[两二三四\d]+天|到达.*(?:办公|现场)"
)
_EMAIL_INTENT = re.compile(r"邮件|发信|通知|告知")
_BOOK_TRANSPORT = re.compile(r"订票|机票|火车|高铁|车票|航班")
_FLIGHT_BOOK = re.compile(r"订机票|机票|航班|飞机|乘机")
_TRAIN_BOOK = re.compile(r"订车票|火车|高铁|动车|铁路|车票(?!站)")
_BOOK_HOTEL = re.compile(r"酒店|住宿|订房")
_CONFIRM = re.compile(r"^(是的|好的|可以|没问题|确认|同意|就这样|按这个|开始吧|执行吧)[。！!？?]*$")
_BOOKING_SELECT = re.compile(
    r"列出|列一下|选项|备选|勾选|让我选|供.?选择|有哪些航班|有哪些酒店|机票.*选|酒店.*选|选哪个|选一个"
)
_PM_PATTERN = re.compile(r"项目经理\s*([\u4e00-\u9fff]{2,4})")


@dataclass
class TravelPlan:
    origin: str | None = None
    destination: str | None = None
    origin_airport: str | None = None
    trip_days: int | None = None
    departure_hint: str | None = None
    return_hint: str | None = None
    arrival_deadline: str | None = None
    needs_email: bool = False
    needs_transport: bool = False
    needs_hotel: bool = False
    email_only: bool = False
    email_recipient: str | None = None
    email_recipient_title: str = "项目经理"
    email_cc: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    email_signature: str | None = None
    transport_pref: str | None = None
    hotel_max_price: int | None = None
    hotel_max_distance_km: float | None = None
    hotel_room_type: str | None = None
    project_name: str | None = None
    location_detail: str | None = None
    staff_level: str | None = None
    raw_goal: str = ""
    travel_purpose: str | None = None


def is_email_workflow_intent(text: str) -> bool:
    return bool(re.search(r"写邮件|邮件|发信|发邮件|写信|email", text, re.I))


def build_default_email_signature(
    structured: dict | None,
    display_name: str = "",
    memory_items: list[dict] | None = None,
) -> str:
    dept = str((structured or {}).get("department") or "").strip()
    name = str((structured or {}).get("display_name") or display_name or "").strip()

    for item in memory_items or []:
        key = str(item.get("key") or "").strip()
        value = str(item.get("value") or "").strip()
        if not value:
            continue
        if key in ("部门", "所属部门") and not dept:
            dept = value
        if key in ("姓名", "名字") and not name:
            name = value

    if dept and name:
        return f"{dept}{name}"
    return dept or name


def build_default_email_subject(plan: TravelPlan) -> str:
    if plan.email_subject:
        return plan.email_subject.strip()
    combined = plan.raw_goal or ""
    subject_match = re.search(r"主题[是为：:\s]*([^\n，,。；;]+)", combined, re.I)
    if subject_match:
        return subject_match.group(1).strip()
    title_match = re.search(r"标题[是为：:\s]*([^\n，,。；;]+)", combined, re.I)
    if title_match:
        return title_match.group(1).strip()
    return f"{plan.destination or '事项'}通知"


def build_default_email_body(plan: TravelPlan, display_name: str = "") -> str:
    if plan.email_body:
        return plan.email_body.strip()
    combined = plan.raw_goal or ""
    body_match = re.search(r"(?:正文|内容|说明|告知)[是为：:\s]*([^\n。；;]+)", combined)
    if body_match:
        return body_match.group(1).strip()
    recipient = plan.email_recipient or "项目经理"
    salutation = infer_salutation(recipient, plan.email_recipient_title)
    sender = display_name.strip() or "我"
    dest = plan.destination or "相关事项"
    if plan.email_only:
        return (
            f"{salutation}\n\n"
            f"您好！{sender}现就{dest}相关安排向您说明，请您知悉。\n\n"
            f"如有需协调事项，烦请指示。"
        )
    days = plan.trip_days or 3
    return (
        f"{salutation}\n\n"
        f"您好！我是{sender}。计划于近期前往{dest}出差，行程约{days}天，"
        f"特此邮件告知并请您知悉相关项目安排。\n\n"
        f"如有需协调事项，烦请指示。"
    )


def enrich_email_plan_from_memory(
    plan: TravelPlan,
    structured: dict | None,
    display_name: str = "",
    memory_items: list[dict] | None = None,
) -> TravelPlan:
    combined = plan.raw_goal or ""
    if not plan.email_cc:
        cc_match = re.search(r"抄送[:：]?\s*([^\n，,。；;]+)", combined)
        plan.email_cc = cc_match.group(1).strip() if cc_match else ""
    if not plan.email_subject:
        plan.email_subject = build_default_email_subject(plan)
    if not plan.email_body:
        plan.email_body = build_default_email_body(plan, display_name)
    if not (plan.email_signature or "").strip():
        plan.email_signature = build_default_email_signature(
            structured, display_name, memory_items
        )
    return plan


def apply_email_plan_draft(plan: TravelPlan, draft: dict | None) -> TravelPlan:
    if not draft:
        return plan
    recipient = str(draft.get("recipient") or draft.get("email_recipient") or "").strip()
    if recipient:
        plan.email_recipient = recipient
    if draft.get("cc") is not None:
        plan.email_cc = str(draft.get("cc") or "").strip()
    if draft.get("subject") is not None:
        plan.email_subject = str(draft.get("subject") or "").strip()
    if draft.get("body") is not None:
        plan.email_body = str(draft.get("body") or "").strip()
    if draft.get("signature") is not None:
        text = str(draft.get("signature") or "").strip()
        if text:
            plan.email_signature = text
    return plan


def configure_email_only_plan(plan: TravelPlan) -> TravelPlan:
    plan.email_only = True
    plan.needs_email = True
    plan.needs_transport = False
    plan.needs_hotel = False
    if not plan.destination:
        plan.destination = "邮件通知"
    if not plan.trip_days:
        plan.trip_days = 1
    return plan


def email_only_missing_slots(plan: TravelPlan) -> list[str]:
    missing: list[str] = []
    if not plan.email_recipient:
        missing.append("收件人")
    if not (plan.email_subject or "").strip():
        missing.append("标题")
    if not (plan.email_body or "").strip():
        missing.append("正文")
    return missing


def is_email_only_ready(plan: TravelPlan) -> bool:
    return len(email_only_missing_slots(plan)) == 0


def can_present_email_confirm(plan: TravelPlan) -> bool:
    return bool(plan.email_recipient)


def build_email_plan_confirm_items(plan: TravelPlan) -> list[dict[str, str]]:
    return [
        _plan_item("收件人", plan.email_recipient),
        _plan_item("抄送人", plan.email_cc or "—"),
        _plan_item("标题", plan.email_subject),
        _plan_item("正文", plan.email_body),
        _plan_item("落款", plan.email_signature),
    ]


def build_email_plan_confirm_metadata(
    plan: TravelPlan,
    *,
    structured: dict | None = None,
    display_name: str = "",
    memory_items: list[dict] | None = None,
) -> dict:
    plan = enrich_email_plan_from_memory(
        plan, structured, display_name, memory_items
    )
    return {
        "interactive": True,
        "travel_plan_confirm": {
            "status": "pending",
            "title": "邮件撰写",
            "items": build_email_plan_confirm_items(plan),
            "needs_transport": False,
            "needs_hotel": False,
            "email_only": True,
            "recipient": plan.email_recipient or "",
            "cc": plan.email_cc or "",
            "subject": plan.email_subject or "",
            "body": plan.email_body or "",
            "signature": plan.email_signature or "",
            "confirm_label": "确认并开始写邮件",
        },
    }


def build_email_plan_confirm_content(
    plan: TravelPlan,
    *,
    updated: bool = False,
    structured: dict | None = None,
    display_name: str = "",
    memory_items: list[dict] | None = None,
) -> str:
    plan = enrich_email_plan_from_memory(
        plan, structured, display_name, memory_items
    )
    intro = (
        "已根据您补充的信息更新邮件内容，请核对："
        if updated
        else "请核对以下邮件内容："
    )
    lines = [intro, ""]
    for item in build_email_plan_confirm_items(plan):
        lines.append(f"- {item['label']}：{item['value']}")
    lines.extend(
        [
            "",
            "👇 请确认无误后点击下方「确认并开始写邮件」，无需再用文字回复。",
        ]
    )
    return "\n".join(lines)


def is_travel_workflow_intent(text: str) -> bool:
    return bool(_TRAVEL_INTENT.search(text))


def is_travel_workflow_intent_with_memory(text: str, structured: dict | None = None) -> bool:
    if is_travel_workflow_intent(text):
        return True
    if structured:
        from src.agent.user_memory import infer_travel_intent_from_memory

        return bool(infer_travel_intent_from_memory(text, structured).get("needs_travel"))
    return False


def apply_memory_travel_hints(
    plan: TravelPlan, structured: dict | None, text: str
) -> TravelPlan:
    if structured:
        from src.agent.user_memory import infer_travel_intent_from_memory

        pref = (structured.get("travel_mode_preference") or "").strip()
        if pref == "飞机" and not plan.transport_pref:
            plan.transport_pref = "经济舱"
            plan.needs_transport = True
        elif pref == "高铁" and not plan.transport_pref:
            plan.transport_pref = "高铁"
            plan.needs_transport = True
        elif pref == "自驾" and not plan.transport_pref:
            plan.transport_pref = "自驾"

        inferred = infer_travel_intent_from_memory(text, structured)
        if not plan.origin:
            base_origin = _origin_from_structured(structured)
            if base_origin:
                plan.origin = base_origin
        if inferred.get("needs_travel"):
            if inferred.get("destination") and not plan.destination:
                plan.destination = str(inferred["destination"])
            if inferred.get("origin") and not plan.origin:
                plan.origin = str(inferred["origin"])
            plan.needs_transport = True
            if inferred.get("needs_booking"):
                plan.needs_transport = True
            if not plan.trip_days:
                plan.trip_days = 1
    return plan


def build_travel_plan(
    messages,
    staff_level: str | None = None,
    *,
    memory_structured: dict | None = None,
) -> TravelPlan:
    combined = merge_user_texts(
        [
            record.content.strip()
            for record in messages
            if getattr(record, "role", None) == "user" and record.content.strip()
        ]
    )
    ctx = parse_travel_context(combined)
    plan = TravelPlan(raw_goal=combined[:200])
    plan.origin = ctx.origin
    plan.destination = ctx.destination
    plan.trip_days = ctx.trip_days or extract_trip_days(combined)
    plan.staff_level = resolve_travel_staff_level(
        memory_structured=memory_structured,
        override=staff_level,
        from_message=ctx.staff_level,
    )
    plan.needs_email = False
    plan.needs_transport = bool(_BOOK_TRANSPORT.search(combined)) or "出差" in combined
    plan.needs_hotel = bool(_BOOK_HOTEL.search(combined))

    if re.search(r"雁宝|燕宝", combined):
        plan.destination = "雁宝"

    if re.search(r"明天", combined):
        plan.departure_hint = "明天"
    if re.search(r"本周四|星期四|周四", combined):
        plan.departure_hint = "本周四"
    if re.search(r"2\s*点\s*前|14\s*点\s*前|下午\s*2\s*点\s*前", combined):
        plan.arrival_deadline = "14:00前"

    airport_match = re.search(r"从?\s*(大兴机场|首都机场|[\u4e00-\u9fff]{2,6}机场)", combined)
    if airport_match:
        plan.origin_airport = airport_match.group(1)
        if "北京" not in (plan.origin or ""):
            plan.origin = plan.origin or "北京"

    yanbao_proj = re.search(r"(雁宝|燕宝)(?:可视化)?(?:二期)?项目", combined)
    if yanbao_proj:
        plan.project_name = yanbao_proj.group(0)
    else:
        project_match = re.search(
            r"([\u4e00-\u9fff]{2,4}(?:可视化)?(?:二期)?项目)",
            combined,
        )
        if project_match and not re.match(r"^[本周明后]", project_match.group(1)):
            plan.project_name = project_match.group(1)

    dest_match = re.search(
        r"去([\u4e00-\u9fff]{2,4})(?:可视化|能源|大厦|二期)?(?:项目)?",
        combined,
    )
    if dest_match and not plan.destination:
        plan.destination = dest_match.group(1)

    price_match = re.search(r"(\d{2,4})\s*元\s*以?内", combined)
    if price_match:
        plan.hotel_max_price = int(price_match.group(1))
    dist_match = re.search(r"(\d+(?:\.\d+)?)\s*公里", combined)
    if dist_match:
        plan.hotel_max_distance_km = float(dist_match.group(1))
    if "标间" in combined or "双床" in combined:
        plan.hotel_room_type = "标间"
    if "北京" in combined and not plan.origin:
        if re.search(r"从\s*北京|北京\s*(?:到|去|出发)", combined):
            plan.origin = "北京"

    pm = _PM_PATTERN.search(combined)
    if pm and is_email_workflow_intent(combined) and not is_travel_workflow_intent(combined):
        plan.email_recipient = pm.group(1)
        plan.email_recipient_title = "项目经理"
    elif is_email_workflow_intent(combined) and not is_travel_workflow_intent(combined):
        notify = re.search(
            r"(?:通知|告知|发给|写给)\s*([\u4e00-\u9fff]{2,4})",
            combined,
        )
        if notify:
            plan.email_recipient = notify.group(1)
        else:
            to_match = re.search(
                r"(?:发邮件给|写邮件给|邮件给|给)\s*([\u4e00-\u9fff]{2,6}(?:经理|总|主任|老师|工)?)",
                combined,
            )
            if to_match:
                plan.email_recipient = to_match.group(1)

    if re.search(r"经济舱|公务舱|二等座|一等座|软席|硬席", combined):
        m = re.search(r"经济舱|公务舱|二等座|一等座|软席|硬席", combined)
        if m:
            plan.transport_pref = m.group(0)

    _finalize_travel_needs(plan, combined)
    _apply_policy_defaults_from_staff_level(plan)
    _apply_travel_schedule_from_text(plan, combined)

    inferred_purpose = _infer_travel_purpose_from_text(combined)
    if inferred_purpose and not plan.travel_purpose:
        plan.travel_purpose = inferred_purpose

    if not plan.origin:
        plan.origin = _origin_from_structured(memory_structured)

    if (
        not plan.trip_days
        and plan.departure_hint
        and (plan.needs_transport or plan.needs_hotel)
    ):
        plan.trip_days = 1

    return plan


_NO_HOTEL = re.compile(r"不住宿|不住酒店|无需酒店|不需要酒店|不用订房")


def _apply_policy_defaults_from_staff_level(plan: TravelPlan) -> None:
    """按差旅人员类别套用住宿限额与交通舱位默认值。"""
    level = plan.staff_level or "其他人员"
    plan.staff_level = level
    if plan.destination and not plan.hotel_max_price:
        limit, _ = accommodation_standard_other(plan.destination)
        plan.hotel_max_price = limit
    if not plan.transport_pref:
        if level == "主要负责人":
            plan.transport_pref = "公务舱"
        elif level == "其他负责人":
            plan.transport_pref = "经济舱"
        else:
            plan.transport_pref = "经济舱"


def _finalize_travel_needs(plan: TravelPlan, combined: str) -> None:
    """补全交通/住宿意图：多日出差默认需要酒店。"""
    if re.search(
        r"办公地点|驻场|(?:到达|抵达|赶到).*(?:办公|现场|神东|鄂尔多斯|雁宝|燕宝)",
        combined,
    ):
        plan.needs_transport = True

    if "出差" in combined or plan.needs_transport or plan.needs_hotel:
        plan.needs_transport = True

    if _NO_HOTEL.search(combined):
        plan.needs_hotel = False
        return

    if _BOOK_HOTEL.search(combined):
        plan.needs_hotel = True
        return

    days = plan.trip_days
    if days is None:
        days = extract_trip_days(combined)
        if days:
            plan.trip_days = days

    if days is not None and days >= 2:
        plan.needs_hotel = True
        return

    if plan.departure_hint and plan.return_hint:
        plan.needs_hotel = True
        if not plan.trip_days or plan.trip_days < 2:
            plan.trip_days = 2
        return

    if re.search(r"后天|大后天|下周|后\s*天", combined) and re.search(
        r"明天|后天|本周|下\s*周", combined
    ):
        plan.needs_hotel = True
        if not plan.trip_days or plan.trip_days < 2:
            plan.trip_days = 2


def missing_slots(plan: TravelPlan) -> list[str]:
    missing: list[str] = []
    if not plan.origin and not plan.origin_airport:
        missing.append("出发地")
    if not plan.destination:
        missing.append("目的地")
    if not plan.departure_hint:
        missing.append("开始时间")
    if not plan.return_hint and not plan.trip_days:
        missing.append("结束时间")
    return missing


def _origin_from_structured(structured: dict | None) -> str | None:
    if not structured:
        return None
    from src.agent.memory_normalizer import extract_city_name

    raw = str(structured.get("base_location") or "").strip()
    if not raw:
        return None
    return extract_city_name(raw) or raw.replace("市", "")


def _is_generic_travel_purpose(value: str) -> bool:
    text = (value or "").strip()
    if len(text) < 2:
        return True
    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", text):
        return True
    if re.match(r"^(出差|差旅|安排|申请|帮我|请帮|请)", text) and len(text) <= 10:
        return True
    return False


def _infer_travel_purpose_from_text(text: str) -> str | None:
    combined = (text or "").strip()
    if not combined:
        return None

    for pattern in (
        r"事由[是为：:\s]+(.+?)(?:[，。；]|$)",
        r"目的[是为：:\s]+(.+?)(?:[，。；]|$)",
        r"为了(.+?)(?:[，。；]|$)",
    ):
        match = re.search(pattern, combined)
        if match:
            value = match.group(1).strip()
            if len(value) >= 2 and not _is_generic_travel_purpose(value):
                return value[:80]

    action_match = re.search(
        r"(?:去|前往|到).{0,18}?(?:参加|开展|进行|完成|做)?"
        r"(.{0,24}?(?:培训|会议|开会|调研|检查|对接|驻场|实施|验收|部署|维护|支持|调试|办事))",
        combined,
    )
    if action_match:
        value = re.sub(r"^(的|去|到|在)", "", action_match.group(1)).strip()
        if len(value) >= 2 and not _is_generic_travel_purpose(value):
            return value[:80]

    for keyword in (
        "现场维护",
        "现场实施",
        "现场支持",
        "现场部署",
        "现场调试",
        "项目会议",
        "项目验收",
        "项目部署",
        "项目上线",
        "项目维护",
        "驻场办公",
        "驻场开发",
        "驻场支持",
        "培训",
        "调研",
        "检查",
        "对接",
        "办事",
    ):
        if keyword in combined:
            project_match = re.search(r"([\u4e00-\u9fff]{2,8}项目)", combined)
            if project_match:
                return f"{project_match.group(1)}{keyword}"[:80]
            return keyword

    meeting_match = re.search(r"([\u4e00-\u9fff]{2,8}项目).{0,8}?(开会|会议)", combined)
    if meeting_match:
        return f"{meeting_match.group(1)}{meeting_match.group(2)}"[:80]

    if re.search(r"开会|会议", combined):
        project_match = re.search(r"([\u4e00-\u9fff]{2,8}项目)", combined)
        if project_match:
            return f"{project_match.group(1)}开会"[:80]
        return "开会"

    return None


def _extract_travel_purpose(plan: TravelPlan) -> str:
    if plan.travel_purpose and plan.travel_purpose.strip():
        return plan.travel_purpose.strip()
    inferred = _infer_travel_purpose_from_text(plan.raw_goal or "")
    return inferred or ""


def _travel_start_label(plan: TravelPlan) -> str:
    if plan.departure_hint:
        return plan.departure_hint
    if plan.trip_days:
        return f"共 {plan.trip_days} 天（待确认具体日期）"
    return "—"


def _travel_end_label(plan: TravelPlan) -> str:
    if plan.return_hint:
        return plan.return_hint
    if plan.trip_days and plan.departure_hint:
        return f"出发后第 {plan.trip_days} 天"
    if plan.trip_days:
        return f"共 {plan.trip_days} 天"
    return "—"


def is_ready_for_transport_booking(plan: TravelPlan) -> bool:
    return bool(plan.destination and (plan.departure_hint or plan.trip_days))


def is_ready_for_hotel_booking(plan: TravelPlan) -> bool:
    return bool(plan.destination and (plan.trip_days or plan.departure_hint))


def missing_transport_booking_slots(plan: TravelPlan) -> list[str]:
    missing: list[str] = []
    if not plan.origin and not plan.origin_airport:
        missing.append("出发地")
    if not plan.destination:
        missing.append("目的地")
    if not plan.departure_hint and not plan.trip_days:
        missing.append("出发日期")
    return missing


def missing_hotel_booking_slots(plan: TravelPlan) -> list[str]:
    missing: list[str] = []
    if not plan.destination:
        missing.append("入住城市")
    if not plan.trip_days and not plan.departure_hint:
        missing.append("入住日期")
    return missing


def is_ready_to_execute(plan: TravelPlan) -> bool:
    return len(missing_slots(plan)) == 0


def wants_booking_selection(text: str) -> bool:
    return bool(_BOOKING_SELECT.search(text))


def can_offer_booking_selection(plan: TravelPlan, text: str) -> bool:
    if not plan.destination:
        return False
    if not (plan.needs_transport or plan.needs_hotel):
        return False
    if is_ready_to_execute(plan):
        return True
    return wants_booking_selection(text)


def _plan_item(label: str, value: str | int | float | None) -> dict[str, str]:
    if value is None or value == "":
        display = "—"
    else:
        display = str(value)
    return {"label": label, "value": display}


TRANSPORT_MODE_OPTIONS = ("飞机", "火车", "自驾", "其他")


def _travel_today() -> date:
    return datetime.now(UTC).date()


_WEEKDAY_CHAR_MAP: dict[str, int] = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
}

_WEEKDAY_TOKEN_RE = re.compile(
    r"(下(?:周|礼拜)|本(?:周|礼拜)|(?:这)?周)?([一二三四五六日])"
)

_WEEKDAY_RANGE_RE = re.compile(
    r"(下(?:周|礼拜)|本(?:周|礼拜)|(?:这)?周)?([一二三四五六日])\s*"
    r"(?:到|至|—|~|-)\s*"
    r"(下(?:周|礼拜)|本(?:周|礼拜)|(?:这)?周)?([一二三四五六日])"
)

_WEEKDAY_DEPARTURE_RE = re.compile(
    r"(下(?:周|礼拜)|本(?:周|礼拜)|(?:这)?周)?([一二三四五六日])\s*"
    r"(?="
    r"(?:上午|下午|早上|晚上|清晨)?\s*(?:的)?(?:机)?(?:票|航班|高铁|火车|动车|车次)"
    r"|(?:出发|去|走|启程|起程)"
    r")"
    r"(?:上午|下午|早上|晚上|清晨)?\s*(?:的)?(?:机)?(?:票|航班|高铁|火车|动车|车次)?"
    r"(?:出发|去|走|启程|起程)?",
)

_WEEKDAY_RETURN_RE = re.compile(
    r"(下(?:周|礼拜)|本(?:周|礼拜)|(?:这)?周)?([一二三四五六日])\s*"
    r"(?:返回|回来|回程|返程|回)(?!收)",
)


def _weekday_char_to_iso(
    weekday_char: str,
    *,
    prefix: str = "",
    today: date | None = None,
) -> str:
    """将「周一 / 下周一 / 本周一」转为 ISO 日期（默认取最近未来 occurrence）。"""
    today = today or _travel_today()
    target = _WEEKDAY_CHAR_MAP.get(weekday_char)
    if target is None:
        return ""
    if prefix.startswith("下"):
        delta = (target - today.weekday()) % 7 + 7
    elif prefix.startswith("本") or prefix in ("周", "这周"):
        delta = (target - today.weekday()) % 7
    else:
        delta = (target - today.weekday()) % 7
        if delta == 0:
            delta = 7
    return (today + timedelta(days=delta)).isoformat()


def _return_weekday_iso(
    departure_iso: str,
    weekday_char: str,
    *,
    prefix: str = "",
    today: date | None = None,
) -> str:
    """结合已解析的出发日，推断返程 weekday（如出发周一 → 返程周三）。"""
    today = today or _travel_today()
    target = _WEEKDAY_CHAR_MAP.get(weekday_char)
    if target is None:
        return ""
    try:
        departure = date.fromisoformat(departure_iso)
    except ValueError:
        departure = today
    if prefix.startswith("下"):
        return _weekday_char_to_iso(weekday_char, prefix=prefix, today=today)
    delta = (target - departure.weekday()) % 7
    if delta == 0:
        delta = 7
    return (departure + timedelta(days=delta)).isoformat()


def resolve_travel_date_hint(hint: str | None) -> date | None:
    """供 mock 查询等模块使用的日期 hint → date。"""
    iso = hint_to_iso(hint)
    if not iso:
        return None
    try:
        return date.fromisoformat(iso)
    except ValueError:
        return None


def hint_to_iso(date_hint: str | None) -> str:
    if not date_hint:
        return ""
    hint = str(date_hint).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", hint):
        return hint
    if hint in ("返回", "回来", "回程"):
        return ""
    today = _travel_today()
    if "大后天" in hint:
        return (today + timedelta(days=3)).isoformat()
    if "后天" in hint:
        return (today + timedelta(days=2)).isoformat()
    if "明天" in hint:
        return (today + timedelta(days=1)).isoformat()
    if "今天" in hint or "今日" in hint:
        return today.isoformat()
    match = re.search(r"下(?:周|礼拜)([一二三四五六日])", hint)
    if match:
        return _weekday_char_to_iso(match.group(1), prefix="下周", today=today)
    match = re.search(r"本(?:周|礼拜)([一二三四五六日])", hint)
    if match:
        return _weekday_char_to_iso(match.group(1), prefix="本周", today=today)
    match = re.search(r"(?:周|礼拜)([一二三四五六日])", hint)
    if match:
        return _weekday_char_to_iso(match.group(1), prefix="", today=today)
    return ""


def _hint_to_iso(date_hint: str | None) -> str:
    return hint_to_iso(date_hint)


def _apply_travel_schedule_from_text(plan: TravelPlan, text: str) -> None:
    """从用户描述解析开始/结束日期，并尽量转为 ISO 供确认卡预填。"""
    if not text.strip():
        return

    today = _travel_today()
    year = today.year

    def parse_md(month: int, day: int, ref_year: int | None = None) -> str:
        try:
            return date(ref_year or year, month, day).isoformat()
        except ValueError:
            return ""

    iso_range = re.search(
        r"(\d{4}-\d{2}-\d{2})\s*(?:到|至|—|~|-)\s*(\d{4}-\d{2}-\d{2})",
        text,
    )
    if iso_range:
        plan.departure_hint = iso_range.group(1)
        plan.return_hint = iso_range.group(2)
        _finalize_trip_days_from_hints(plan)
        return

    weekday_range = _WEEKDAY_RANGE_RE.search(text)
    if weekday_range:
        dep_prefix = weekday_range.group(1) or ""
        dep_char = weekday_range.group(2)
        ret_prefix = weekday_range.group(3) or ""
        ret_char = weekday_range.group(4)
        dep_iso = _weekday_char_to_iso(dep_char, prefix=dep_prefix, today=today)
        if dep_iso:
            plan.departure_hint = dep_iso
            ret_iso = _return_weekday_iso(
                dep_iso, ret_char, prefix=ret_prefix, today=today
            )
            if ret_iso:
                plan.return_hint = ret_iso
        _finalize_trip_days_from_hints(plan)
        return

    md_range = re.search(
        r"(\d{1,2})\s*月\s*(\d{1,2})\s*[号日]?\s*(?:到|至|—|-)\s*"
        r"(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*[号日]",
        text,
    )
    if md_range:
        start_month = int(md_range.group(1))
        start_day = int(md_range.group(2))
        end_month = int(md_range.group(3)) if md_range.group(3) else start_month
        end_day = int(md_range.group(4))
        start_iso = parse_md(start_month, start_day)
        end_iso = parse_md(end_month, end_day)
        if start_iso:
            plan.departure_hint = start_iso
        if end_iso:
            plan.return_hint = end_iso
        _finalize_trip_days_from_hints(plan)
        return

    dep_match = _WEEKDAY_DEPARTURE_RE.search(text)
    if dep_match:
        dep_iso = _weekday_char_to_iso(
            dep_match.group(2),
            prefix=dep_match.group(1) or "",
            today=today,
        )
        if dep_iso:
            plan.departure_hint = dep_iso

    ret_match = _WEEKDAY_RETURN_RE.search(text)
    if ret_match:
        ret_prefix = ret_match.group(1) or ""
        ret_char = ret_match.group(2)
        if plan.departure_hint and re.match(
            r"^\d{4}-\d{2}-\d{2}$", str(plan.departure_hint)
        ):
            ret_iso = _return_weekday_iso(
                str(plan.departure_hint),
                ret_char,
                prefix=ret_prefix,
                today=today,
            )
        else:
            ret_iso = _weekday_char_to_iso(
                ret_char, prefix=ret_prefix, today=today
            )
        if ret_iso:
            plan.return_hint = ret_iso

    if not plan.departure_hint or not re.match(
        r"^\d{4}-\d{2}-\d{2}$", str(plan.departure_hint)
    ):
        md_start = re.search(
            r"(\d{1,2})\s*月\s*(\d{1,2})\s*[号日](?:\s*(?:出发|去|走|起程|启程))?",
            text,
        )
        if md_start:
            iso = parse_md(int(md_start.group(1)), int(md_start.group(2)))
            if iso:
                plan.departure_hint = iso
        elif not plan.departure_hint:
            tokens = list(_WEEKDAY_TOKEN_RE.finditer(text))
            if len(tokens) >= 2 and not ret_match:
                first = tokens[0]
                second = tokens[1]
                dep_iso = _weekday_char_to_iso(
                    first.group(2),
                    prefix=first.group(1) or "",
                    today=today,
                )
                if dep_iso:
                    plan.departure_hint = dep_iso
                    ret_iso = _return_weekday_iso(
                        dep_iso,
                        second.group(2),
                        prefix=second.group(1) or "",
                        today=today,
                    )
                    if ret_iso:
                        plan.return_hint = ret_iso
            elif len(tokens) == 1 and not dep_match:
                token = tokens[0]
                dep_iso = _weekday_char_to_iso(
                    token.group(2),
                    prefix=token.group(1) or "",
                    today=today,
                )
                if dep_iso:
                    plan.departure_hint = dep_iso

    if not plan.return_hint or not re.match(
        r"^\d{4}-\d{2}-\d{2}$", str(plan.return_hint)
    ):
        md_return = re.search(
            r"(\d{1,2})\s*月\s*(\d{1,2})\s*[号日]?\s*(?:返回|回来|回程|回)",
            text,
        )
        if md_return:
            iso = parse_md(int(md_return.group(1)), int(md_return.group(2)))
            if iso:
                plan.return_hint = iso
        iso_return = re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:返回|回来|回程)", text)
        if iso_return:
            plan.return_hint = iso_return.group(1)

    for field in ("departure_hint", "return_hint"):
        value = getattr(plan, field)
        if value and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
            iso = hint_to_iso(str(value))
            if iso:
                setattr(plan, field, iso)

    if (
        plan.departure_hint
        and re.match(r"^\d{4}-\d{2}-\d{2}$", str(plan.departure_hint))
        and not plan.return_hint
    ):
        days = plan.trip_days or extract_trip_days(text)
        if not days and re.search(r"机票|航班|车票|火车|高铁|订票|出差|差旅", text):
            days = 3
        if days and days >= 2:
            plan.trip_days = days
            try:
                start = date.fromisoformat(str(plan.departure_hint))
                plan.return_hint = (
                    start + timedelta(days=max(days - 1, 0))
                ).isoformat()
            except ValueError:
                pass

    _finalize_trip_days_from_hints(plan)


def _finalize_trip_days_from_hints(plan: TravelPlan) -> None:
    if (
        plan.departure_hint
        and re.match(r"^\d{4}-\d{2}-\d{2}$", str(plan.departure_hint))
        and plan.return_hint
        and re.match(r"^\d{4}-\d{2}-\d{2}$", str(plan.return_hint))
    ):
        try:
            start = date.fromisoformat(str(plan.departure_hint))
            end = date.fromisoformat(str(plan.return_hint))
            plan.trip_days = max((end - start).days + 1, 1)
        except ValueError:
            pass
    elif (
        plan.departure_hint
        and re.match(r"^\d{4}-\d{2}-\d{2}$", str(plan.departure_hint))
        and plan.trip_days
        and not plan.return_hint
    ):
        try:
            start = date.fromisoformat(str(plan.departure_hint))
            plan.return_hint = (
                start + timedelta(days=max(plan.trip_days - 1, 0))
            ).isoformat()
        except ValueError:
            pass


def _resolve_transport_mode_label(plan: TravelPlan) -> tuple[str, str]:
    pref = (plan.transport_pref or "").strip()
    if not pref:
        return "飞机", ""
    if "自驾" in pref:
        return "自驾", ""
    if re.search(r"高铁|火车|二等|一等|软席|硬席", pref):
        return "火车", ""
    if re.search(r"飞机|航班|经济舱|公务舱|舱", pref):
        return "飞机", ""
    return "其他", pref


def _transport_mode_display(mode: str, other: str = "") -> str:
    if mode == "其他" and other.strip():
        return other.strip()
    return mode or "飞机"


def travel_plan_confirm_fields(plan: TravelPlan) -> dict[str, str]:
    mode, other = _resolve_transport_mode_label(plan)
    start_iso = _hint_to_iso(plan.departure_hint)
    end_iso = _hint_to_iso(plan.return_hint)
    if not end_iso and start_iso and plan.trip_days:
        try:
            start = datetime.fromisoformat(start_iso).date()
            end_iso = (start + timedelta(days=max(plan.trip_days - 1, 0))).isoformat()
        except ValueError:
            pass
    purpose = _extract_travel_purpose(plan)
    return {
        "origin": plan.origin or plan.origin_airport or "",
        "destination": plan.destination or "",
        "start_date": start_iso,
        "end_date": end_iso,
        "purpose": purpose,
        "transport_mode": mode,
        "transport_other": other,
    }


def apply_travel_plan_draft(plan: TravelPlan, draft: dict | None) -> TravelPlan:
    """合并确认卡片填写；与对话解析冲突时，以卡片非空字段为准。"""
    if not draft:
        return plan

    origin = str(draft.get("origin") or "").strip()
    if origin:
        plan.origin = origin

    destination = str(draft.get("destination") or "").strip()
    if destination:
        plan.destination = destination

    start_date = str(draft.get("start_date") or "").strip()
    if start_date:
        plan.departure_hint = start_date

    end_date = str(draft.get("end_date") or "").strip()
    if end_date:
        plan.return_hint = end_date

    if start_date and end_date:
        try:
            start = datetime.fromisoformat(start_date).date()
            end = datetime.fromisoformat(end_date).date()
            plan.trip_days = max((end - start).days + 1, 1)
        except ValueError:
            pass

    if draft.get("purpose") is not None:
        purpose = str(draft.get("purpose") or "").strip()
        plan.travel_purpose = purpose or None

    transport_mode = str(draft.get("transport_mode") or "").strip()
    transport_other = str(draft.get("transport_other") or "").strip()
    if transport_mode == "飞机":
        plan.transport_pref = "经济舱"
    elif transport_mode == "火车":
        plan.transport_pref = "高铁"
    elif transport_mode == "自驾":
        plan.transport_pref = "自驾"
    elif transport_mode == "其他":
        plan.transport_pref = transport_other or "其他"

    return plan


def travel_plan_confirm_items(plan: TravelPlan) -> list[dict[str, str]]:
    fields = travel_plan_confirm_fields(plan)
    mode, other = _resolve_transport_mode_label(plan)
    return [
        _plan_item("出发地", fields["origin"]),
        _plan_item("目的地", fields["destination"]),
        _plan_item("开始时间", fields["start_date"] or _travel_start_label(plan)),
        _plan_item("结束时间", fields["end_date"] or _travel_end_label(plan)),
        _plan_item("出差目的", fields["purpose"] or "—"),
        _plan_item("交通方式", _transport_mode_display(mode, other)),
    ]


def is_travel_plan_update(text: str) -> bool:
    """待确认出差单存在时，识别用户的补充/修正说明。"""
    if is_plan_revision_text(text):
        return True
    if _TRAVEL_INTENT.search(text):
        return True
    if _EMAIL_INTENT.search(text) or _BOOK_TRANSPORT.search(text) or _BOOK_HOTEL.search(text):
        return True
    if _PM_PATTERN.search(text):
        return True
    if re.search(r"明天|后天|周[一二三四五六日]|项目|经理|目的地|出发|返回|天数|天", text):
        return True
    return False


def build_travel_plan_confirm_content(plan: TravelPlan, *, updated: bool = False) -> str:
    if updated:
        return "已根据您补充的信息更新，请在下方卡片中核对并确认。"
    return "请在下方卡片中核对差旅信息，确认无误后点击「确认开始办理」。"


def build_travel_plan_confirm_metadata(plan: TravelPlan) -> dict:
    fields = travel_plan_confirm_fields(plan)
    return {
        "interactive": True,
        "travel_plan_confirm": {
            "status": "pending",
            "title": f"{plan.destination or '差旅'}出差单确认",
            "items": travel_plan_confirm_items(plan),
            "confirm_label": "确认并开始办理差旅单",
            **fields,
        },
    }


def resolve_transport_booking_type(text: str, plan: TravelPlan | None = None) -> str:
    """根据用户话术或差旅单交通方式，判定展示航班还是火车备选。"""
    if _FLIGHT_BOOK.search(text):
        return "flight"
    if _TRAIN_BOOK.search(text):
        return "train"
    if plan is not None:
        mode, _ = _resolve_transport_mode_label(plan)
        if mode == "飞机":
            return "flight"
        if mode == "火车":
            return "train"
    return "train"


def build_booking_selection_content(
    plan: TravelPlan,
    *,
    booking_kind: str | None = None,
    transport_type: str | None = None,
) -> str:
    dest = plan.destination or "目的地"
    origin = plan.origin or "北京"
    if booking_kind == "transport":
        mode = transport_type or resolve_transport_booking_type("", plan)
        label = "航班" if mode == "flight" else "火车/高铁"
        lines = [
            f"已为您查询「{origin} → {dest}」的可选{label}方案。",
            "",
            f"- 出发地：{origin}；目的地：{dest}",
        ]
        if plan.departure_hint:
            lines.append(f"- 出发时间：{plan.departure_hint}")
        pick_hint = "航班" if mode == "flight" else "车次"
        lines.extend(
            [
                "",
                f"👇 **请在下方点选{pick_hint}**，选好后点击「确认预订」。",
            ]
        )
        return "\n".join(lines)

    if booking_kind == "hotel":
        days = plan.trip_days or 1
        lines = [
            f"已为您查询「{dest}」的可选酒店方案。",
            "",
            f"- 入住城市：{dest}；约 {days} 天",
        ]
        if plan.hotel_max_price:
            lines.append(f"- 酒店预算：{plan.hotel_max_price} 元/晚以内")
        lines.extend(
            [
                "",
                "👇 **请在下方点选酒店**，选好后点击「确认预订」。",
            ]
        )
        return "\n".join(lines)

    days = plan.trip_days or 1
    lines = [
        f"信息已齐全，已为您查询「{dest}出差」的可选方案。",
        "",
        f"- 出发地：{origin}；目的地：{dest}；出差约 {days} 天",
    ]
    if plan.arrival_deadline:
        lines.append(f"- 到达要求：{plan.arrival_deadline}")
    if plan.hotel_max_price:
        lines.append(f"- 酒店预算：{plan.hotel_max_price} 元/晚以内")
    if plan.location_detail:
        lines.append(f"- 项目地点：**{plan.location_detail}**（已由项目映射表解析）")
    lines.extend(
        [
            "",
            "👇 **请先选择航班/车票，再选择酒店**（各选一项），选好后点击「确认预订」。",
        ]
    )
    return "\n".join(lines)


def build_booking_selection_metadata(
    plan: TravelPlan,
    booking: dict,
    *,
    booking_kind: str | None = None,
    transport_type: str | None = None,
    user_text: str = "",
) -> dict:
    if booking_kind == "transport":
        needs_flight, needs_hotel = True, False
        mode = transport_type or resolve_transport_booking_type(user_text, plan)
    elif booking_kind == "hotel":
        needs_flight, needs_hotel = False, True
        mode = None
    else:
        needs_flight = plan.needs_transport
        needs_hotel = plan.needs_hotel
        mode = resolve_transport_booking_type(user_text, plan) if plan.needs_transport else None
    selection: dict = {
        "status": "pending",
        "booking_kind": booking_kind,
        "needs_flight": needs_flight,
        "needs_hotel": needs_hotel,
        "destination": plan.destination or "",
        "flights": booking.get("flights") or [],
        "trains": booking.get("trains") or [],
        "hotels": booking.get("hotels") or [],
    }
    if mode:
        selection["transport_type"] = mode
    return {
        "interactive": True,
        "booking_selection": selection,
    }


def build_execution_summary(
    plan: TravelPlan,
    sender_name: str,
    task_id: str,
    booking: dict | None = None,
) -> str:
    dest = plan.destination or "目的地"
    origin = plan.origin or "北京"
    days = plan.trip_days or 3
    limit, label = accommodation_standard_other(dest)
    staff = plan.staff_level or "其他人员"
    hours = estimate_train_hours(origin, dest)
    transport_line = f"{origin}→{dest}"
    if hours and hours >= 6 and staff == "其他人员":
        transport_line += f"，铁路约 {hours:g} 小时，可按细则乘坐火车软席"
    elif plan.transport_pref:
        transport_line += f"，交通方式：{plan.transport_pref}"
    elif staff == "其他人员":
        transport_line += "，交通：高铁/飞机（经济舱/二等座）"
    else:
        transport_line += f"，交通：按{staff}标准预订"

    lines = [
        f"差旅单信息已确认，已为您创建「{dest}出差申请」任务，请点击下方任务卡片继续办理。",
        "",
        "一、差旅概要",
        f"- 出发地：{origin}；目的地：{dest}",
        f"- 开始时间：{_travel_start_label(plan)}；结束时间：{_travel_end_label(plan)}",
    ]
    purpose = _extract_travel_purpose(plan)
    if purpose:
        lines.append(f"- 出差目的：{purpose}")
    lines.extend(
        [
            f"- 住宿参考：{label} {staff}标准 {limit} 元/人·天",
            "",
        ]
    )

    step_no = 2
    flights = (booking or {}).get("flights") or []
    hotels = (booking or {}).get("hotels") or []

    if flights:
        section_title = f"{'三' if step_no == 3 else '二'}、交通预订"
        lines.extend([section_title])
        chosen = flights[0]
        lines.append(
            f"- 已选航班 {chosen.get('flight_no')}（{chosen.get('airline')}）"
            f" {chosen.get('origin')} → {chosen.get('destination')}"
        )
        lines.append(
            f"  出发 {chosen.get('departure_time')}，到达 {chosen.get('arrival_time')}，"
            f"{chosen.get('cabin')}，参考价 {chosen.get('price')} 元"
        )
        lines.append("")
        step_no += 1

    if hotels:
        cn = "二三四五六七八"[min(step_no - 2, 7)] if step_no >= 2 else str(step_no)
        lines.extend([f"{cn}、酒店预订"])
        chosen = hotels[0]
        lines.append(
            f"- 已选 {chosen.get('name')}，{chosen.get('address')}，"
            f"{chosen.get('room_type')}，{chosen.get('price_per_night')} 元/晚"
        )
        lines.append(
            f"  入住 {chosen.get('check_in')} 至 {chosen.get('check_out')}"
        )
        lines.append("")

    lines.append("请点击下方任务卡片查看各步骤详情、表单预览与确认。")
    return "\n".join(lines)


def build_task_metadata(plan: TravelPlan, task_id: str) -> dict:
    return {
        "task_id": task_id,
        "task_title": f"{plan.destination or '出差'}差旅申请",
        "progress": "1/2",
        "progress_percent": 50,
        "steps_desc": "差旅申请 · 用户确认",
    }


def build_transport_task_metadata(plan: TravelPlan, task_id: str, flight: dict) -> dict:
    dest = plan.destination or flight.get("destination") or "目的地"
    flight_no = flight.get("flight_no") or "—"
    return {
        "task_id": task_id,
        "task_title": f"{dest}·订车票",
        "progress": "1/2",
        "progress_percent": 50,
        "steps_desc": "交通预订 · 用户确认",
        "booking_kind": "transport",
        "category": "transport_book",
    }


def build_hotel_task_metadata(plan: TravelPlan, task_id: str, hotel: dict) -> dict:
    dest = plan.destination or "目的地"
    name = hotel.get("name") or "酒店"
    return {
        "task_id": task_id,
        "task_title": f"{dest}·订酒店",
        "progress": "1/2",
        "progress_percent": 50,
        "steps_desc": "酒店预订 · 用户确认",
        "booking_kind": "hotel",
        "category": "hotel_book",
    }


def build_booking_tasks_execution_summary(
    plan: TravelPlan,
    related_metas: list[dict],
) -> str:
    dest = plan.destination or "目的地"
    lines = [
        f"已确认「{dest}」出行方案，请分别在下方卡片中完成交通与酒店预订：",
        "",
    ]
    for meta in related_metas:
        kind = meta.get("booking_kind")
        title = meta.get("task_title") or "预订"
        if kind == "transport":
            lines.append(f"- **{title}**：点击卡片进入 OA 交通预订，填写乘客信息并提交确认。")
        elif kind == "hotel":
            lines.append(f"- **{title}**：点击卡片进入 OA 酒店预订，填写入住信息并提交确认。")
        else:
            lines.append(f"- **{title}**：点击卡片继续办理。")
    lines.extend(
        [
            "",
            "完成 OA 确认后，卡片进度将自动更新为 2/2。",
        ]
    )
    return "\n".join(lines)


def build_email_execution_summary(plan: TravelPlan, task_id: str) -> str:
    recipient = plan.email_recipient or "收件人"
    subject = (plan.email_subject or "").strip() or "（未填写主题）"
    return "\n".join(
        [
            "邮件内容已确认，正在为您打开 Outlook 邮件撰写页面。",
            "",
            f"- 收件人：{recipient}",
            f"- 主题：{subject}",
            "",
            "您可在邮件页面继续编辑、保存草稿或直接发送；发送后可在「已发送」中查看并撤回（演示）。",
        ]
    )


def build_email_task_metadata(
    plan: TravelPlan,
    task_id: str,
    form_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    title = (plan.email_subject or "写邮件").strip()[:80]
    return {
        "task_id": task_id,
        "task_title": title,
        "progress": "1/2",
        "progress_percent": 50,
        "steps_desc": "邮件撰写 · 用户确认",
        "email_compose": {
            "task_id": task_id,
            "session_id": session_id or "",
            "form_id": form_id,
            "recipient": plan.email_recipient or "",
            "cc": plan.email_cc or "",
            "subject": plan.email_subject or "",
            "body": plan.email_body or "",
            "signature": plan.email_signature or "",
        },
    }
