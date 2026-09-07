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
    ("gn_meeting", "国能会", re.compile(r"国能会|国能会议|线上会议|视频会议")),
    ("email", "写邮件", re.compile(r"写邮件|邮件|发信|发邮件|写信|email", re.I)),
    ("room", "会议室", re.compile(r"会议室|预约.*会议|订.*会议|预订会议|约.{0,12}会议|约.{0,8}会|帮我约")),
    ("travel", "差旅单", re.compile(r"出差|差旅(?:申请|单)?|驻场|办公地点")),
    ("booking", "订车票", re.compile(r"订(?:机)?票|订车票|订机票|机票|航班|高铁|火车(?!站)")),
    ("hotel", "订酒店", re.compile(r"酒店|住宿|订房|入住|住\s*[两二三四五六七八九十\d]+\s*天|住\s*\d+\s*晚")),
    ("workpackage", "填工时", re.compile(r"工时|工包|填报")),
    ("leave", "办请假", re.compile(r"请假|休假|补假")),
    ("info_collect", "填信息", re.compile(r"填信息|信息收集|信息采集|个人信息|完善资料|长期记忆")),
)

_DISPLAY_ORDER = [item[0] for item in _NODE_DEFS]
_LABELS = {item[0]: item[1] for item in _NODE_DEFS}
_PATTERNS = {item[0]: item[2] for item in _NODE_DEFS}

_TASK_CATEGORY_TO_NODE: dict[str, str] = {
    "workpackage": "workpackage",
    "leave": "leave",
    "info_collect": "info_collect",
    "meeting": "room",
    "gn_meeting": "gn_meeting",
    "travel": "travel",
    "email": "email",
    "transport_book": "booking",
    "hotel_book": "hotel",
}

_NODE_TO_SERVICE: dict[str, str] = {
    "gn_meeting": "meeting",
    "room": "meeting",
    "workpackage": "workpackage",
    "leave": "leave",
    "info_collect": "info_collect",
    "travel": "travel",
    "booking": "travel",
    "hotel": "travel",
    "email": "travel",
}

_NODE_GUIDANCE: dict[str, str] = {
    "gn_meeting": "请说明国能会议主题、会议时间与参会人员，例如：「明天下午2点开项目评审国能会议，参会张明和李经理」。",
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
    if has_transport or re.search(r"订(?:机)?票|订车票|机票|航班|高铁|火车(?!站)|车票", text):
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


def match_node_from_text(text: str) -> str | None:
    """从当前用户消息识别其想办理的节点（按展示顺序取首个命中）。"""
    stripped = (text or "").strip()
    if not stripped:
        return None
    for node_id in _DISPLAY_ORDER:
        if _PATTERNS[node_id].search(stripped):
            return node_id
    return None


def match_plan_node_from_text(text: str, plan: dict[str, Any]) -> str | None:
    node_id = match_node_from_text(text)
    if not node_id or _node_by_id(plan, node_id) is None:
        return None
    return node_id


def activate_plan_node(plan: dict[str, Any], node_id: str) -> bool:
    """激活指定节点；已提交 OA 的其他节点不阻塞并行办理。"""
    node_id = _resolve_node_for_activation(plan, node_id)
    node = _node_by_id(plan, node_id)
    if node is None or node.get("status") == "completed":
        return False
    if node.get("status") == "pending":
        node["status"] = "running"
    plan["active_node_id"] = node_id
    _enforce_booking_before_hotel(plan)
    return True


def service_for_node(node_id: str | None) -> str | None:
    if not node_id:
        return None
    return _NODE_TO_SERVICE.get(node_id)


SERVICE_ALLOWED_NODES: dict[str, frozenset[str]] = {
    "meeting": frozenset({"gn_meeting", "room"}),
    "travel": frozenset({"travel", "booking", "hotel", "email"}),
    "workpackage": frozenset({"workpackage"}),
    "leave": frozenset({"leave"}),
    "info_collect": frozenset({"info_collect"}),
}


def is_parallel_workflow_plan(wf_plan: dict[str, Any] | None) -> bool:
    return bool(
        wf_plan
        and isinstance(wf_plan.get("nodes"), list)
        and len(wf_plan["nodes"]) >= 2
    )


def activated_plan_node(text: str, wf_plan: dict[str, Any] | None) -> str | None:
    """用户当前消息显式激活的计划节点（含订酒店→订车票等重定向）。"""
    if not wf_plan:
        return None
    node_id = match_plan_node_from_text(text, wf_plan)
    if not node_id:
        return None
    return _resolve_node_for_activation(wf_plan, node_id)


def should_service_handle_activation(
    service: str,
    user_content: str,
    wf_plan: dict[str, Any] | None,
) -> bool:
    """多节点并行时，各 workflow 只处理用户显式激活的本服务节点。"""
    if not is_parallel_workflow_plan(wf_plan):
        return True
    node_id = activated_plan_node(user_content, wf_plan)
    if not node_id:
        return True
    allowed = SERVICE_ALLOWED_NODES.get(service)
    if not allowed:
        return True
    return node_id in allowed


async def prepare_workflow_route(
    message_repo,
    session_id: str,
    text: str,
) -> str | None:
    """根据会话计划与用户当前消息，决定优先路由的工作流服务。"""
    plan = await get_workflow_plan_from_session(message_repo, session_id)
    node_id = match_node_from_text(text)
    if plan is not None:
        plan_node = match_plan_node_from_text(text, plan)
        if plan_node:
            plan_node = _resolve_node_for_activation(plan, plan_node)
            activate_plan_node(plan, plan_node)
            await _persist_workflow_plan(message_repo, session_id, plan)
            return service_for_node(plan_node)
        active_id = plan.get("active_node_id")
        active = _node_by_id(plan, active_id) if active_id else None
        if active and active.get("status") == "submitted":
            _prepare_parallel_after_submit(plan)
            await _persist_workflow_plan(message_repo, session_id, plan)
            return service_for_node(plan.get("active_node_id"))
        return service_for_node(active_id)
    return service_for_node(node_id)


def _prepare_parallel_after_submit(plan: dict[str, Any]) -> None:
    """某节点已提交 OA 后，将焦点切换到下一个可并行办理的节点。"""
    for node in _nodes_in_display_order(plan):
        if node.get("id") == "hotel" and not _booking_gate_open(plan):
            continue
        if node.get("status") == "pending":
            node["status"] = "running"
            plan["active_node_id"] = node.get("id")
            return
    for node in _nodes_in_display_order(plan):
        if node.get("status") == "running":
            plan["active_node_id"] = node.get("id")
            return
    plan["active_node_id"] = None


def build_initial_workflow_plan(text: str) -> dict[str, Any] | None:
    nodes = detect_workflow_nodes(text)
    if len(nodes) < 2:
        return None
    active_id = nodes[0]["id"]
    plan = {
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
    _normalize_plan_nodes(plan)
    return plan


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
    _normalize_plan_nodes(plan)
    _enforce_booking_before_hotel(plan)
    meta = dict(record.metadata_json or {})
    meta[_PLAN_META_KEY] = plan
    await message_repo.update(record, metadata_json=meta)


def _nodes_in_display_order(plan: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = plan.get("nodes")
    if not isinstance(nodes, list):
        return []
    order_index = {node_id: idx for idx, node_id in enumerate(_DISPLAY_ORDER)}
    known = [n for n in nodes if isinstance(n, dict) and n.get("id") in order_index]
    known.sort(key=lambda n: order_index[str(n["id"])])
    unknown = [n for n in nodes if isinstance(n, dict) and n.get("id") not in order_index]
    return known + unknown


def _normalize_plan_nodes(plan: dict[str, Any]) -> None:
    ordered = _nodes_in_display_order(plan)
    if ordered:
        plan["nodes"] = ordered


def _booking_gate_open(plan: dict[str, Any]) -> bool:
    booking = _node_by_id(plan, "booking")
    if booking is None:
        return True
    return booking.get("status") in ("submitted", "completed")


def _resolve_node_for_activation(plan: dict[str, Any], node_id: str) -> str:
    if node_id == "hotel" and not _booking_gate_open(plan):
        if _node_by_id(plan, "booking") is not None:
            return "booking"
    return node_id


def _enforce_booking_before_hotel(plan: dict[str, Any]) -> bool:
    """订酒店须待订车票完成后才可推进；仅在酒店节点抢焦点时重定向到订车票。"""
    hotel = _node_by_id(plan, "hotel")
    booking = _node_by_id(plan, "booking")
    if hotel is None or booking is None or _booking_gate_open(plan):
        return False

    active_id = plan.get("active_node_id")
    hotel_wants_focus = active_id == "hotel" or hotel.get("status") == "running"
    if not hotel_wants_focus:
        return False

    changed = False
    if hotel.get("status") == "running":
        hotel["status"] = "pending"
        changed = True
    if booking.get("status") == "pending":
        booking["status"] = "running"
        plan["active_node_id"] = "booking"
        changed = True
    elif active_id == "hotel":
        plan["active_node_id"] = "booking"
        changed = True
    return changed


def _node_by_id(plan: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    nodes = plan.get("nodes")
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if isinstance(node, dict) and node.get("id") == node_id:
            return node
    return None


def _advance_active_node(plan: dict[str, Any]) -> None:
    for node in _nodes_in_display_order(plan):
        if node.get("id") == "hotel" and not _booking_gate_open(plan):
            continue
        if node.get("status") == "pending":
            node["status"] = "running"
            plan["active_node_id"] = node.get("id")
            return
    for node in _nodes_in_display_order(plan):
        if node.get("status") == "running":
            plan["active_node_id"] = node.get("id")
            return
    plan["active_node_id"] = None


def _ensure_valid_active_node(plan: dict[str, Any]) -> None:
    _normalize_plan_nodes(plan)
    _enforce_booking_before_hotel(plan)
    active_id = plan.get("active_node_id")
    if not active_id:
        return
    node = _node_by_id(plan, active_id)
    if node and node.get("status") in ("completed", "submitted"):
        _advance_active_node(plan)
    _enforce_booking_before_hotel(plan)


def _node_id_for_task_meta(task_meta: dict[str, Any]) -> str | None:
    kind = task_meta.get("meeting_kind")
    if kind == "gn":
        return "gn_meeting"
    if kind == "room":
        return "room"
    category = str(task_meta.get("category") or "")
    if category in _TASK_CATEGORY_TO_NODE:
        return _TASK_CATEGORY_TO_NODE[category]
    steps_desc = str(task_meta.get("steps_desc") or "")
    if "国能会议" in steps_desc or "国能会" in steps_desc:
        return "gn_meeting"
    if "会议室" in steps_desc or "会议预约" in steps_desc:
        return "room"
    if "工时" in steps_desc:
        return "workpackage"
    if "请假" in steps_desc:
        return "leave"
    if "差旅" in steps_desc:
        return "travel"
    return None


async def link_tasks_from_assistant_metadata(
    message_repo,
    session_id: str,
    metadata: dict[str, Any],
) -> None:
    """任务创建早于 workflow_plan 落库时，在助手消息写入后补关联 task_id。"""
    plan = await get_workflow_plan_from_session(message_repo, session_id)
    if plan is None:
        return

    candidates: list[tuple[str, dict[str, Any]]] = []
    root_tid = metadata.get("task_id")
    if root_tid:
        candidates.append((str(root_tid), metadata))
    related = metadata.get("related_tasks")
    if isinstance(related, list):
        for item in related:
            if isinstance(item, dict) and item.get("task_id"):
                tid = str(item["task_id"])
                if not any(tid == existing for existing, _ in candidates):
                    candidates.append((tid, item))

    for task_id, task_meta in candidates:
        node_id = _node_id_for_task_meta(task_meta)
        if node_id and _node_by_id(plan, node_id) is not None:
            await link_task_to_plan(
                message_repo,
                session_id,
                task_id,
                node_id=node_id,
            )


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
    for raw_target_id in target_ids:
        target_id = _resolve_node_for_activation(plan, raw_target_id)
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
    *,
    task_steps: list[dict] | None = None,
) -> dict[str, Any] | None:
    from src.agent.task_catalog import infer_category

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

    if not matched and task_steps:
        category = infer_category(task_steps)
        node_id = _TASK_CATEGORY_TO_NODE.get(category)
        if node_id:
            node = _node_by_id(plan, node_id)
            if node is not None:
                node["task_id"] = task_id
                matched = [node]
                changed = True

    if not matched:
        return plan

    for node in matched:
        if node.get("status") == status:
            continue
        node["status"] = status
        changed = True

    if status == "submitted":
        _prepare_parallel_after_submit(plan)
        changed = True

    if status == "completed":
        prev_active = plan.get("active_node_id")
        matched_active = any(
            plan.get("active_node_id") == node.get("id") for node in matched
        )
        if matched_active:
            _advance_active_node(plan)
        else:
            active = _node_by_id(plan, plan.get("active_node_id") or "")
            if active and active.get("status") == "completed":
                _advance_active_node(plan)
        if plan.get("active_node_id") != prev_active:
            changed = True

    _normalize_plan_nodes(plan)
    if _enforce_booking_before_hotel(plan):
        changed = True

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
            if not re.search(r"国能会|国能会议|线上|视频", combined) and "国能会议时间" not in missing:
                if not has_meeting_schedule(plan):
                    missing.append("国能会议时间")
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


async def build_session_results_summary(
    message_repo,
    session_id: str,
    plan: dict[str, Any],
) -> str:
    records = await message_repo.list_recent_for_context(session_id, limit=80)
    lines = [
        "══════════════════════════════════════",
        "  智能办公助手 · 本次办理结果汇总",
        "══════════════════════════════════════",
        "",
        "【办理节点】",
    ]

    for node in _nodes_in_display_order(plan):
        label = str(node.get("label") or node.get("id") or "—")
        status = str(node.get("status") or "pending")
        if status == "completed":
            mark = "✅ 已完成"
        elif status == "submitted":
            mark = "🟡 审批中"
        elif status == "running":
            mark = "🔵 进行中"
        else:
            mark = "⬜ 待开始"
        lines.append(f"  · {label}：{mark}")

    lines.extend(["", "【办理详情】"])
    seen_tasks: set[str] = set()
    detail_count = 0

    for record in reversed(records):
        meta = record.metadata_json or {}
        tid = meta.get("task_id")
        if meta.get("oa_completion") and tid and tid not in seen_tasks:
            seen_tasks.add(tid)
            detail_count += 1
            title = str(meta.get("task_title") or "办事任务")
            category = str(meta.get("category") or "")
            lines.append(f"  {detail_count}. {title}")
            if category == "transport_book":
                lines.append("     类型：交通预订 · 状态：已确认")
            elif category == "hotel_book":
                lines.append("     类型：酒店预订 · 状态：已确认")
            elif category == "travel":
                lines.append("     类型：差旅申请 · 状态：已审批通过")
            elif category == "gn_meeting":
                lines.append("     类型：国能会议 · 状态：已创建")
            elif category == "meeting":
                lines.append("     类型：会议室预约 · 状态：已确认")
            else:
                lines.append(f"     类型：{category or '综合办事'} · 状态：已完成")
            lines.append("")

        gn = meta.get("gn_meeting_result")
        if isinstance(gn, dict) and gn.get("meeting_link"):
            key = f"gn:{gn.get('meeting_link')}"
            if key not in seen_tasks:
                seen_tasks.add(key)
                detail_count += 1
                lines.append(f"  {detail_count}. 国能会议")
                lines.append(f"     主题：{gn.get('subject') or '—'}")
                lines.append(f"     链接：{gn.get('meeting_link')}")
                if gn.get("meeting_password"):
                    lines.append(f"     密码：{gn.get('meeting_password')}")
                lines.append("")

        room = meta.get("room_booking_result")
        if isinstance(room, dict) and room.get("room_name"):
            key = f"room:{room.get('room_name')}"
            if key not in seen_tasks:
                seen_tasks.add(key)
                detail_count += 1
                lines.append(f"  {detail_count}. 会议室预约")
                lines.append(f"     会议室：{room.get('room_name')}")
                lines.append(f"     时间：{room.get('start_time')} — {room.get('end_time')}")
                lines.append("")

        email_sent = meta.get("email_sent_result")
        if isinstance(email_sent, dict) and email_sent.get("recipient"):
            key = f"email:{email_sent.get('message_id') or email_sent.get('recipient')}"
            if key not in seen_tasks:
                seen_tasks.add(key)
                detail_count += 1
                lines.append(f"  {detail_count}. 邮件通知")
                lines.append(f"     收件人：{email_sent.get('recipient')}")
                lines.append(f"     主题：{email_sent.get('subject') or '—'}")
                lines.append("")

    if detail_count == 0:
        lines.append("  （暂无结构化结果，请查看上方对话记录）")
        lines.append("")

    lines.extend(
        [
            "──────────────────────────────────────",
            "如需继续办理其他事项，请直接告诉我。",
            "══════════════════════════════════════",
        ]
    )
    return "\n".join(lines)


async def build_next_node_guidance(
    message_repo,
    session_id: str,
    plan: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    _ensure_valid_active_node(plan)
    await _persist_workflow_plan(message_repo, session_id, plan)
    active_id = plan.get("active_node_id")
    nodes = plan.get("nodes")
    if not active_id or not isinstance(nodes, list):
        completed_labels = [
            str(node.get("label"))
            for node in nodes
            if isinstance(node, dict) and node.get("status") == "completed"
        ] if isinstance(nodes, list) else []
        summary = "、".join(completed_labels) if completed_labels else "全部事项"
        copy_text = await build_session_results_summary(message_repo, session_id, plan)
        content = "\n".join(
            [
                "🎉 **全部办理节点已完成**",
                "",
                f"已完成：{summary}。",
                "",
                "以下为本次办理结果汇总，您可一键复制保存：",
            ]
        )
        return content, {
            "workflow_next_node": {"node_id": None, "label": None, "missing_slots": []},
            "workflow_plan": plan,
            "workflow_session_summary": {"text": copy_text},
        }

    node = _node_by_id(plan, active_id)
    if node is None:
        return "", None

    label = str(node.get("label") or _LABELS.get(active_id, active_id))
    ctx = await load_session_context(message_repo, session_id)
    missing = _missing_slots_for_node(active_id, ctx.user_messages)
    meeting_plan = build_meeting_plan(ctx.user_messages) if active_id == "room" else None
    submitted_labels = [
        str(item.get("label") or "")
        for item in nodes
        if isinstance(item, dict) and item.get("status") == "submitted"
    ]

    lines = [
        "**接下来请办理：**" + label,
        "",
    ]
    if submitted_labels:
        waiting = "、".join(label for label in submitted_labels if label)
        lines.append(f"「{waiting}」仍在 OA 审批中，您可并行准备本节点信息。")
        lines.append("")
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

    hotel_node = _node_by_id(plan, "hotel")
    if (
        active_id == "booking"
        and hotel_node is not None
        and hotel_node.get("status") not in ("submitted", "completed")
    ):
        lines.append("")
        lines.append("订酒店将在订车票完成后继续办理。")

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
