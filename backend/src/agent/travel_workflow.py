"""差旅办事流程：槽位收集、就绪判定、任务与表单生成。"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    email_recipient: str | None = None
    email_recipient_title: str = "项目经理"
    transport_pref: str | None = None
    hotel_max_price: int | None = None
    hotel_max_distance_km: float | None = None
    hotel_room_type: str | None = None
    project_name: str | None = None
    location_detail: str | None = None
    staff_level: str | None = None
    raw_goal: str = ""


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
    plan.needs_email = bool(_EMAIL_INTENT.search(combined))
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
    if re.search(r"返回\s*北京|回\s*北京|回\s*[\u4e00-\u9fff]{2,4}", combined):
        plan.return_hint = "返回北京" if "北京" in combined else "返回"
    if "北京" in combined and not plan.origin:
        if re.search(r"返回\s*北京|回\s*北京|从\s*北京", combined):
            plan.origin = "北京"

    pm = _PM_PATTERN.search(combined)
    if pm:
        plan.email_recipient = pm.group(1)
        plan.email_recipient_title = "项目经理"
    else:
        notify = re.search(
            r"(?:通知|告知|发给|写给)\s*([\u4e00-\u9fff]{2,4})",
            combined,
        )
        if notify:
            plan.email_recipient = notify.group(1)

    if re.search(r"经济舱|公务舱|二等座|一等座|软席|硬席", combined):
        m = re.search(r"经济舱|公务舱|二等座|一等座|软席|硬席", combined)
        if m:
            plan.transport_pref = m.group(0)

    _finalize_travel_needs(plan, combined)
    _apply_policy_defaults_from_staff_level(plan)

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
    if not plan.destination:
        missing.append("目的地")
    if not plan.trip_days and not (plan.departure_hint and plan.return_hint):
        missing.append("出差天数或往返时间")
    if plan.needs_email and not plan.email_recipient:
        missing.append("邮件收件人")
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


def travel_plan_confirm_items(plan: TravelPlan) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    items.append(_plan_item("出发地", plan.origin or plan.origin_airport or "北京"))
    items.append(_plan_item("目的地", plan.destination))
    if plan.location_detail:
        items.append(_plan_item("项目地点", plan.location_detail))
    if plan.project_name:
        items.append(_plan_item("关联项目", plan.project_name))
    days = plan.trip_days
    if days:
        items.append(_plan_item("出差天数", f"{days} 天"))
    if plan.departure_hint:
        items.append(_plan_item("出发时间", plan.departure_hint))
    if plan.return_hint:
        items.append(_plan_item("返回安排", plan.return_hint))
    if plan.arrival_deadline:
        items.append(_plan_item("到达要求", plan.arrival_deadline))
    if plan.needs_transport:
        items.append(_plan_item("交通预订", plan.transport_pref or "机票/火车"))
    if plan.needs_hotel:
        hotel = "需要"
        if plan.hotel_max_price:
            hotel += f"，预算 {plan.hotel_max_price} 元/晚以内"
        if plan.hotel_room_type:
            hotel += f"，{plan.hotel_room_type}"
        items.append(_plan_item("酒店预订", hotel))
    if plan.needs_email and plan.email_recipient:
        items.append(_plan_item("邮件通知", plan.email_recipient))
    return items


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
    intro = (
        "已根据您补充的信息更新出差安排，请核对："
        if updated
        else "信息已收集完毕，请核对以下出差安排："
    )
    lines = [
        intro,
        "",
    ]
    for item in travel_plan_confirm_items(plan):
        lines.append(f"- {item['label']}：{item['value']}")
    lines.extend(
        [
            "",
            "👇 请确认无误后点击下方「确认开始办理」，无需再用文字回复。",
        ]
    )
    return "\n".join(lines)


def build_travel_plan_confirm_metadata(plan: TravelPlan) -> dict:
    return {
        "interactive": True,
        "travel_plan_confirm": {
            "status": "pending",
            "title": f"{plan.destination or '出差'}行程安排",
            "items": travel_plan_confirm_items(plan),
            "needs_transport": plan.needs_transport,
            "needs_hotel": plan.needs_hotel,
        },
    }


def build_booking_selection_content(plan: TravelPlan) -> str:
    dest = plan.destination or "目的地"
    origin = plan.origin or "北京"
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
            "👇 **请在下方勾选框中直接点选**航班与酒店（各选一项），选好后点击「确认预订」。",
        ]
    )
    return "\n".join(lines)


def build_booking_selection_metadata(plan: TravelPlan, booking: dict) -> dict:
    return {
        "interactive": True,
        "booking_selection": {
            "status": "pending",
            "needs_flight": plan.needs_transport,
            "needs_hotel": plan.needs_hotel,
            "destination": plan.destination or "",
            "flights": booking.get("flights") or [],
            "hotels": booking.get("hotels") or [],
        },
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
        f"信息已齐全，已为您启动「{dest}出差」办理流程，当前进展如下：",
        "",
        "一、行程概要",
        f"- 出发地：{origin}；目的地：{dest}；出差约 {days} 天",
        f"- {transport_line}",
        f"- 住宿参考：{label} {staff}标准 {limit} 元/人·天",
        "",
    ]

    if plan.needs_email and plan.email_recipient:
        salutation = infer_salutation(plan.email_recipient, plan.email_recipient_title)
        lines.extend(
            [
                "二、邮件通知",
                f"- 已生成致 {salutation} 的出差通知邮件草稿，请在任务卡片中查看并确认发送",
                "",
            ]
        )

    step_no = 3 if plan.needs_email else 2
    flights = (booking or {}).get("flights") or []
    hotels = (booking or {}).get("hotels") or []

    if plan.needs_transport:
        section_title = f"{'三' if step_no == 3 else '二'}、交通预订"
        lines.extend([section_title])
        if flights:
            chosen = flights[0]
            lines.append(
                f"- 已选航班 {chosen.get('flight_no')}（{chosen.get('airline')}）"
                f" {chosen.get('origin')} → {chosen.get('destination')}"
            )
            lines.append(
                f"  出发 {chosen.get('departure_time')}，到达 {chosen.get('arrival_time')}，"
                f"{chosen.get('cabin')}，参考价 {chosen.get('price')} 元"
            )
        else:
            lines.append(f"- 已提交 {origin}→{dest} 去程票务查询，状态：处理中")
        lines.append("")
        step_no += 1

    if plan.needs_hotel:
        cn = "二三四五六七八"[min(step_no - 2, 7)] if step_no >= 2 else str(step_no)
        lines.extend([f"{cn}、酒店预订"])
        if hotels:
            chosen = hotels[0]
            lines.append(
                f"- 已选 {chosen.get('name')}，{chosen.get('address')}，"
                f"{chosen.get('room_type')}，{chosen.get('price_per_night')} 元/晚"
            )
            lines.append(
                f"  入住 {chosen.get('check_in')} 至 {chosen.get('check_out')}"
            )
        else:
            lines.extend(
                [
                    f"- 已提交 {dest} 酒店 {days - 1 if days > 1 else 1} 晚查询，"
                    f"限额 {plan.hotel_max_price or limit} 元/晚"
                ]
            )
        lines.append("")

    lines.append("请点击下方任务卡片查看各步骤详情、表单预览与确认。")
    return "\n".join(lines)


def build_task_metadata(plan: TravelPlan, task_id: str) -> dict:
    steps = ["差旅申请"]
    if plan.needs_email:
        steps.append("邮件通知")
    if plan.needs_transport:
        steps.append("交通预订")
    if plan.needs_hotel:
        steps.append("酒店预订")
    steps.append("用户确认")
    total = len(steps)
    current = min(2, total)
    return {
        "task_id": task_id,
        "task_title": f"{plan.destination or '出差'}差旅安排",
        "progress": f"{current}/{total}",
        "progress_percent": int(current / total * 100),
        "steps_desc": " · ".join(steps),
    }
