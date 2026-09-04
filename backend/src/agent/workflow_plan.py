"""多意图工作流节点计划：识别、状态推进与任务关联。"""

from __future__ import annotations

import re
from typing import Any

from src.agent.leave_workflow import build_leave_plan, missing_slots as leave_missing_slots
from src.agent.info_collect_workflow import (
    build_personal_info_plan,
    missing_slots as info_collect_missing_slots,
)
from src.agent.meeting_workflow import build_meeting_plan, has_meeting_schedule, missing_slots as meeting_missing_slots
from src.agent.session_context import load_session_context, merge_user_texts
from src.agent.travel_policy_rules import extract_trip_days
from src.agent.travel_workflow import build_travel_plan, missing_slots as travel_missing_slots
from src.agent.workpackage_workflow import (
    build_workpackage_plan,
    missing_slots as workpackage_missing_slots,
    normalize_workpackage_plan,
)
from src.agent.workflow_queue import split_intent_segments

_PLAN_META_KEY = "workflow_plan"

_NODE_DEFS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("gn_meeting", "国能会", re.compile(r"国能会|线上会议|视频会议")),
    ("email", "写邮件", re.compile(r"邮件|发信|发邮件|写信|email", re.I)),
    ("room", "会议室", re.compile(r"会议室|预约.*会议|订.*会议|预订会议|约.{0,12}会议|约.{0,8}会|帮我约")),
    ("travel", "差旅单", re.compile(r"出差|差旅(?:申请)?|驻场|办公地点")),
    ("booking", "订车票", re.compile(r"订票|机票|航班|车票|高铁|火车")),
    ("hotel", "订酒店", re.compile(r"酒店|住宿|订房|入住|住\s*[两二三四五六七八九十\d]+\s*天|住\s*\d+\s*晚")),
    ("workpackage", "填工时", re.compile(r"工时|工包|填报")),
    ("leave", "办请假", re.compile(r"请假|休假|补假")),
    ("info_collect", "填信息", re.compile(r"信息收集|信息采集|个人信息|完善资料|长期记忆")),
)

_DISPLAY_ORDER = [item[0] for item in _NODE_DEFS]
_LABELS = {item[0]: item[1] for item in _NODE_DEFS}
_PATTERNS = {item[0]: item[2] for item in _NODE_DEFS}

_TASK_CATEGORY_TO_NODE: dict[str, str] = {
    "workpackage": "workpackage",
    "leave": "leave",
    "info_collect": "info_collect",
    "meeting": "room",
    "travel": "travel",
    "email": "email",
}

_NODE_GUIDANCE: dict[str, str] = {
    "gn_meeting": "请说明国能会主题、会议时间与参会人员，例如：「明天下午2点开项目评审国能会，参会张明和李经理」。",
    "email": "请说明邮件收件人、主题和主要通知内容，例如：「发邮件给张经理，主题出差安排确认」。",
    "room": "请说明会议时间与设备要求，例如：「今晚7点开会，有投屏的会议室哪个都行」。",
    "travel": "请说明目的地、出差日期和事由，例如：「下周三去鄂尔多斯出差2天，现场培训」。",
    "booking": "请说明出发地、目的地、出发日期和交通方式，例如：「订下周三北京到鄂尔多斯机票」。",
    "hotel": "请说明入住城市、入住与离店日期及预算，例如：「在鄂尔多斯神东办公区附近订2晚酒店，500元/晚以内」。",
    "workpackage": "请说明项目名称、填报周期和天数，例如：「帮我在神东项目填本周5天工时」。",
    "leave": "请说明请假时间和事由，例如：「下周四请事假一天，家里有事」。",
    "info_collect": "请补充您的核心个人信息，例如：「我叫张明，工号 0176338，Base 北京，部门智能矿山事业部」。",
}

_IMPLICIT_TRAVEL_CONTEXT = re.compile(
    r"办公地点|驻场|现场(?:办公|办事|培训)|"
    r"(?:到达|抵达|赶到|前往).{0,16}(?:办公|现场|项目|神东|鄂尔多斯|雁宝|燕宝)|"
    r"在(?:那儿|那里|当地|神东|鄂尔多斯).{0,10}(?:住|待|办公)|"
    r"住\s*[两二三四五六七八九十\d]+\s*天|住\s*\d+\s*晚"
)
_TRANSPORT_HINT = re.compile(
    r"机票|航班|火车|高铁|车票|订票|"
    r"(?:周[一二三四五六日天]|明天|后天|大后天).{0,10}(?:到|抵达|到达)"
)
_REMOTE_SITE = re.compile(r"神东|雁宝|燕宝|鄂尔多斯|办公地点|驻场|项目现场")
_STAY_HINT = re.compile(r"住\s*[两二三四五六七八九十\d]+\s*天|住\s*\d+\s*晚")


def _infer_implicit_travel_nodes(text: str) -> set[str]:
    """从「机票 + 外地办公点 + 住 N 天」等表述推断差旅/订票/酒店节点。"""
    found: set[str] = set()
    if not text.strip():
        return found

    has_stay = bool(_STAY_HINT.search(text))
    has_travel_context = bool(_IMPLICIT_TRAVEL_CONTEXT.search(text))
    has_transport = bool(_TRANSPORT_HINT.search(text))
    has_remote = bool(_REMOTE_SITE.search(text))
    trip_days = extract_trip_days(text)

    implies_trip = has_travel_context or (
        has_remote and (has_stay or has_transport or bool(re.search(r"到达|抵达|赶到", text)))
    )

    if implies_trip:
        found.add("travel")
    if has_transport or re.search(r"订票|机票|航班|高铁|火车|车票", text):
        found.add("booking")
    if has_stay or re.search(r"酒店|住宿|订房|入住", text):
        found.add("hotel")
    elif implies_trip and trip_days is not None and trip_days >= 2:
        found.add("hotel")

    return found


def detect_workflow_nodes(text: str) -> list[dict[str, str]]:
    segments = split_intent_segments(text)
    search_parts = segments if len(segments) > 1 else [text.strip()]
    found_set: set[str] = set()
    for node_id in _DISPLAY_ORDER:
        pattern = _PATTERNS[node_id]
        for part in search_parts:
            if pattern.search(part):
                found_set.add(node_id)
                break
    combined = " ".join(search_parts)
    found_set |= _infer_implicit_travel_nodes(combined)
    found_ids = [node_id for node_id in _DISPLAY_ORDER if node_id in found_set]
    return [{"id": node_id, "label": _LABELS[node_id]} for node_id in found_ids]


def build_initial_workflow_plan(text: str) -> dict[str, Any] | None:
    nodes = detect_workflow_nodes(text)
    if len(nodes) < 2:
        return None
    active_id = nodes[0]["id"]
    return {
        "nodes": [
            {
                "id": node["id"],
                "label": node["label"],
                "status": "running" if node["id"] == active_id else "pending",
                "task_id": None,
            }
            for node in nodes
        ],
        "active_node_id": active_id,
    }


async def get_workflow_plan_from_session(message_repo, session_id: str) -> dict[str, Any] | None:
    record = await message_repo.find_workflow_plan_message(session_id)
    if record is None:
        return None
    meta = record.metadata_json or {}
    plan = meta.get(_PLAN_META_KEY)
    return dict(plan) if isinstance(plan, dict) else None


async def enrich_metadata_with_workflow_plan(
    message_repo,
    session_id: str,
    metadata: dict | None,
    session_text: str,
) -> dict | None:
    if await get_workflow_plan_from_session(message_repo, session_id):
        return metadata
    plan = build_initial_workflow_plan(session_text)
    if plan is None:
        return metadata
    meta = dict(metadata or {})
    meta[_PLAN_META_KEY] = plan
    return meta


async def _persist_workflow_plan(message_repo, session_id: str, plan: dict[str, Any]) -> None:
    record = await message_repo.find_workflow_plan_message(session_id)
    if record is None:
        return
    meta = dict(record.metadata_json or {})
    meta[_PLAN_META_KEY] = plan
    await message_repo.update(record, metadata_json=meta)


def _node_by_id(plan: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    nodes = plan.get("nodes")
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if isinstance(node, dict) and node.get("id") == node_id:
            return node
    return None


def _advance_active_node(plan: dict[str, Any]) -> None:
    nodes = plan.get("nodes")
    if not isinstance(nodes, list):
        return
    next_node = next(
        (node for node in nodes if isinstance(node, dict) and node.get("status") == "pending"),
        None,
    )
    if next_node is None:
        plan["active_node_id"] = None
        return
    next_node["status"] = "running"
    plan["active_node_id"] = next_node.get("id")


async def link_task_to_plan(
    message_repo,
    session_id: str,
    task_id: str,
    *,
    category: str | None = None,
    node_id: str | None = None,
    extra_node_ids: list[str] | None = None,
) -> None:
    plan = await get_workflow_plan_from_session(message_repo, session_id)
    if plan is None:
        return

    target_ids: list[str] = []
    if node_id:
        target_ids.append(node_id)
    elif category:
        mapped = _TASK_CATEGORY_TO_NODE.get(category)
        if mapped:
            target_ids.append(mapped)
    for extra in extra_node_ids or []:
        if extra not in target_ids:
            target_ids.append(extra)

    changed = False
    for target_id in target_ids:
        node = _node_by_id(plan, target_id)
        if node is None:
            continue
        node["task_id"] = task_id
        if node.get("status") in (None, "pending"):
            node["status"] = "running"
            plan["active_node_id"] = target_id
        changed = True

    if changed:
        await _persist_workflow_plan(message_repo, session_id, plan)


async def update_plan_for_task(
    message_repo,
    session_id: str,
    task_id: str,
    status: str,
) -> dict[str, Any] | None:
    plan = await get_workflow_plan_from_session(message_repo, session_id)
    if plan is None:
        return None

    changed = False
    nodes = plan.get("nodes")
    if not isinstance(nodes, list):
        return None

    matched: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("task_id") == task_id:
            matched.append(node)

    if not matched:
        return plan

    for node in matched:
        if node.get("status") == status:
            continue
        node["status"] = status
        changed = True

    if status == "completed":
        for node in matched:
            if plan.get("active_node_id") == node.get("id"):
                _advance_active_node(plan)
                break

    if changed:
        await _persist_workflow_plan(message_repo, session_id, plan)
    return plan


def _missing_slots_for_node(node_id: str, user_messages) -> list[str]:
    combined = merge_user_texts(
        [
            record.content.strip()
            for record in user_messages
            if getattr(record, "role", None) == "user" and record.content.strip()
        ]
    )

    if node_id == "workpackage":
        plan = normalize_workpackage_plan(build_workpackage_plan(user_messages))
        return workpackage_missing_slots(plan)

    if node_id == "leave":
        plan = build_leave_plan(user_messages)
        missing = leave_missing_slots(plan)
        if not plan.reason:
            missing.append("请假事由")
        return missing

    if node_id == "info_collect":
        plan = build_personal_info_plan(user_messages, {})
        return info_collect_missing_slots(plan)

    if node_id in ("room", "gn_meeting"):
        plan = build_meeting_plan(user_messages)
        missing = meeting_missing_slots(plan)
        if has_meeting_schedule(plan):
            missing = [slot for slot in missing if slot != "会议日期或时段"]
        if node_id == "gn_meeting":
            if not plan.subject:
                if "会议主题" not in missing:
                    missing.insert(0, "会议主题")
            if not re.search(r"国能会|线上|视频", combined) and "国能会时间" not in missing:
                if not has_meeting_schedule(plan):
                    missing.append("国能会时间")
            if not plan.attendees and "参会人员" not in missing:
                missing.append("参会人员")
        return missing

    if node_id == "travel":
        plan = build_travel_plan(user_messages)
        return travel_missing_slots(plan)

    if node_id == "email":
        plan = build_travel_plan(user_messages)
        missing: list[str] = []
        if not plan.email_recipient:
            missing.append("收件人")
        if not re.search(r"主题|标题|subject", combined, re.I):
            missing.append("邮件主题")
        if not re.search(r"通知|告知|内容|说明", combined):
            missing.append("邮件正文要点")
        return missing

    if node_id == "booking":
        plan = build_travel_plan(user_messages)
        missing = []
        if not plan.origin and not re.search(r"从.+出发|出发地", combined):
            missing.append("出发地")
        if not plan.destination:
            missing.append("目的地")
        if not plan.departure_hint:
            missing.append("出发日期")
        if not plan.transport_pref and not re.search(r"机票|航班|高铁|火车", combined):
            missing.append("交通方式")
        return missing

    if node_id == "hotel":
        plan = build_travel_plan(user_messages)
        missing = []
        if not plan.destination:
            missing.append("入住城市")
        if not plan.trip_days and not plan.departure_hint:
            missing.append("入住日期")
        if not plan.trip_days and not re.search(r"住\s*[两二三四\d]+天|住\s*\d+晚", combined):
            missing.append("入住晚数")
        return missing

    return []


async def build_next_node_guidance(
    message_repo,
    session_id: str,
    plan: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    active_id = plan.get("active_node_id")
    nodes = plan.get("nodes")
    if not active_id or not isinstance(nodes, list):
        completed_labels = [
            str(node.get("label"))
            for node in nodes
            if isinstance(node, dict) and node.get("status") == "completed"
        ] if isinstance(nodes, list) else []
        summary = "、".join(completed_labels) if completed_labels else "全部事项"
        content = "\n".join(
            [
                "🎉 **全部办理节点已完成**",
                "",
                f"已完成：{summary}。如需继续其他事项，请直接告诉我。",
            ]
        )
        return content, {
            "workflow_next_node": {"node_id": None, "label": None, "missing_slots": []},
            "workflow_plan": plan,
        }

    node = _node_by_id(plan, active_id)
    if node is None:
        return "", None

    label = str(node.get("label") or _LABELS.get(active_id, active_id))
    ctx = await load_session_context(message_repo, session_id)
    missing = _missing_slots_for_node(active_id, ctx.user_messages)
    meeting_plan = build_meeting_plan(ctx.user_messages) if active_id == "room" else None

    lines = [
        "**接下来请办理：**" + label,
        "",
    ]
    if missing:
        lines.append(f"还需要您补充：**{'、'.join(missing)}**")
        lines.append("")
        if active_id == "room" and meeting_plan and has_meeting_schedule(meeting_plan):
            lines.append("会议时间已从对话中识别，请在下方卡片中核对时段并确认。")
        else:
            lines.append(_NODE_GUIDANCE.get(active_id, "请补充相关信息后继续办理。"))
    else:
        if active_id == "room" and meeting_plan and has_meeting_schedule(meeting_plan):
            lines.append("会议时间已从对话中识别，请在下方卡片中核对并确认。")
        else:
            lines.append("相关信息已从对话中识别，您可以直接说「开始办理」或补充细节后继续。")
        hint = _NODE_GUIDANCE.get(active_id)
        if hint and not (active_id == "room" and meeting_plan and has_meeting_schedule(meeting_plan)):
            lines.append("")
            lines.append(hint)

    metadata = {
        "workflow_next_node": {
            "node_id": active_id,
            "label": label,
            "missing_slots": missing,
        },
        "workflow_plan": plan,
    }
    return "\n".join(lines), metadata


def append_next_node_guidance(completion_content: str, guidance: str) -> str:
    if not guidance.strip():
        return completion_content
    return f"{completion_content.rstrip()}\n\n---\n\n{guidance.strip()}"


def node_ids_for_travel_task(
    plan: dict[str, Any] | None,
    needs_transport: bool,
    needs_hotel: bool = False,
) -> list[str]:
    if plan is None:
        return []
    node_ids = ["travel"]
    if needs_transport and _node_by_id(plan, "booking") is not None:
        node_ids.append("booking")
    if needs_hotel and _node_by_id(plan, "hotel") is not None:
        node_ids.append("hotel")
    return node_ids
