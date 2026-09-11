"""多意图工作流节点计划：识别、状态推进与任务关联。"""

from __future__ import annotations

import copy
import re
from datetime import datetime
from typing import Any

from src.agent.leave_workflow import (
    build_leave_plan,
    build_leave_plan_confirm_metadata,
    missing_slots as leave_missing_slots,
)
from src.agent.info_collect_workflow import (
    build_personal_info_plan,
    missing_slots as info_collect_missing_slots,
)
from src.agent.meeting_workflow import (
    build_meeting_plan,
    build_meeting_plan_confirm_metadata,
    can_present_meeting_confirm,
    has_meeting_schedule,
    meeting_plan_for_node,
    sync_meeting_plan_with_workflow_nodes,
    missing_slots as meeting_missing_slots,
)
from src.agent.session_context import load_session_context, merge_user_texts
from src.agent.travel_policy_rules import extract_trip_days
from src.agent.travel_workflow import (
    build_travel_plan,
    missing_slots as travel_missing_slots,
    resolve_transport_booking_type,
)
from src.agent.workpackage_workflow import (
    build_workpackage_plan,
    missing_slots as workpackage_missing_slots,
    normalize_workpackage_plan,
)
from src.agent.workflow_queue import split_intent_segments

_PLAN_META_KEY = "workflow_plan"

_NODE_DEFS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("gn_meeting", "国能会", re.compile(
        r"国能会|国能会议|线上会议|视频会议|线上会|线上\s*会|线上.{0,8}会"
    )),
    ("email", "写邮件", re.compile(r"写邮件|邮件|发信|发邮件|写信|email", re.I)),
    ("room", "会议室", re.compile(r"会议室|预约.*会议|订.*会议|预订会议|约.{0,12}会议|约.{0,8}会|帮我约")),
    ("travel", "差旅单", re.compile(r"出差|差旅(?:申请|单)?|驻场|办公地点")),
    ("booking", "订车票", re.compile(r"订.*?(?:机)?票|订.*?车票|订车票|订机票|机票|航班|高铁|火车(?!站)|车票")),
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
    from src.agent.travel_workflow import is_booking_cancel_intent

    found: set[str] = set()
    if not text.strip():
        return found
    if is_booking_cancel_intent(text):
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
    from src.agent.meeting_workflow import detect_meeting_modes

    needs_gn, needs_room = detect_meeting_modes(combined)
    if needs_gn:
        found_set.add("gn_meeting")
    if needs_room:
        found_set.add("room")
    found_ids = [node_id for node_id in _DISPLAY_ORDER if node_id in found_set]
    return [{"id": node_id, "label": _LABELS[node_id]} for node_id in found_ids]


def match_node_from_text(text: str) -> str | None:
    """从当前用户消息识别其想办理的节点（按展示顺序取首个命中）。"""
    stripped = (text or "").strip()
    if not stripped:
        return None
    from src.agent.travel_workflow import is_booking_cancel_intent

    if is_booking_cancel_intent(stripped):
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
    """激活指定节点；已提交 OA 的节点不再被文本匹配抢回办理焦点。"""
    node_id = _resolve_node_for_activation(plan, node_id)
    node = _node_by_id(plan, node_id)
    if node is None:
        return False
    if node.get("status") in ("completed", "submitted"):
        return False
    if node.get("status") in ("pending", "cancelled"):
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


def is_workflow_plan_complete(wf_plan: dict[str, Any] | None) -> bool:
    if not wf_plan:
        return False
    nodes = wf_plan.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return False
    return all(
        isinstance(node, dict) and node.get("status") == "completed"
        for node in nodes
    )


def should_service_handle_activation(
    service: str,
    user_content: str,
    wf_plan: dict[str, Any] | None,
) -> bool:
    """多节点并行时，各 workflow 只处理用户显式激活的本服务节点。"""
    if not is_parallel_workflow_plan(wf_plan):
        return True

    if is_workflow_plan_complete(wf_plan):
        from src.agent.travel_workflow import (
            is_booking_cancel_intent,
            is_transport_or_travel_booking_intent,
        )
        from src.agent.meeting_workflow import (
            is_meeting_workflow_intent_current,
            is_room_cancel_intent,
        )

        node_id = match_node_from_text(user_content)
        if node_id:
            allowed = SERVICE_ALLOWED_NODES.get(service)
            if not allowed:
                return service_for_node(node_id) == service
            return node_id in allowed
        if service == "travel":
            return is_transport_or_travel_booking_intent(user_content) or is_booking_cancel_intent(
                user_content
            )
        if service == "meeting":
            return is_meeting_workflow_intent_current(user_content) or is_room_cancel_intent(
                user_content
            )
        return False

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
    from src.agent.travel_workflow import is_transport_or_travel_booking_intent
    from src.agent.workflow_cancel import is_workflow_cancel_intent, resolve_workflow_cancel_node

    plan = await get_workflow_plan_from_session(message_repo, session_id)
    if plan is not None:
        plan, _changed = await sync_workflow_plan_with_message(
            message_repo, session_id, text
        )
    node_id = match_node_from_text(text)
    if plan is not None and is_workflow_plan_complete(plan):
        if node_id:
            return service_for_node(node_id)
        if is_workflow_cancel_intent(text, plan):
            cancel_node = resolve_workflow_cancel_node(text, plan)
            if cancel_node:
                return service_for_node(cancel_node)
        if is_transport_or_travel_booking_intent(text):
            return "travel"
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
            _prepare_parallel_after_submit(plan, after_node_id=str(active_id or ""))
            await _persist_workflow_plan(message_repo, session_id, plan)
            return service_for_node(plan.get("active_node_id"))
        return service_for_node(active_id)
    return service_for_node(node_id)


def _prepare_parallel_after_submit(
    plan: dict[str, Any],
    *,
    after_node_id: str | None = None,
) -> None:
    """某节点已提交 OA 后，将焦点切换到下一个可并行办理的节点。"""
    _advance_active_node(plan, after_node_id=after_node_id)


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


def expand_workflow_plan_from_text(
    plan: dict[str, Any],
    text: str,
    *,
    activate: bool = True,
) -> tuple[dict[str, Any], bool]:
    """将用户新消息中的办理意图并入已有流程计划（仅追加缺失节点）。"""
    from src.agent.workflow_cancel import is_workflow_cancel_intent

    stripped = (text or "").strip()
    if not stripped or is_workflow_cancel_intent(stripped, plan):
        return plan, False

    detected = detect_workflow_nodes(stripped)
    detected_ids = {item["id"] for item in detected}

    single = match_node_from_text(stripped)
    if single and single not in detected_ids:
        detected.append({"id": single, "label": _LABELS[single]})
    if activate and _is_confirm_action_text(stripped):
        activate = False

    nodes = plan.get("nodes")
    if not isinstance(nodes, list):
        return plan, False

    existing_ids = {
        str(node.get("id"))
        for node in nodes
        if isinstance(node, dict) and node.get("id")
    }
    changed = False
    for item in detected:
        node_id = item["id"]
        if node_id in existing_ids:
            continue
        nodes.append(
            {
                "id": node_id,
                "label": item["label"],
                "status": "pending",
                "task_id": None,
            }
        )
        existing_ids.add(node_id)
        changed = True

    if activate and single and _node_by_id(plan, single) is not None:
        if activate_plan_node(plan, single):
            changed = True

    if changed:
        _normalize_plan_nodes(plan)
        _enforce_booking_before_hotel(plan)
    return plan, changed


async def sync_workflow_plan_with_message(
    message_repo,
    session_id: str,
    user_content: str,
) -> tuple[dict[str, Any] | None, bool]:
    """根据用户最新一句补充流程节点，并持久化到会话计划。"""
    existing = await get_workflow_plan_from_session(message_repo, session_id)
    if existing is None:
        return None, False

    ctx = await load_session_context(message_repo, session_id, user_content=user_content)
    combined = merge_user_texts(
        [
            record.content.strip()
            for record in ctx.user_messages
            if getattr(record, "role", None) == "user" and record.content.strip()
        ]
    )

    plan = copy.deepcopy(existing)
    _, changed_latest = expand_workflow_plan_from_text(plan, user_content, activate=True)
    _, changed_full = expand_workflow_plan_from_text(plan, combined, activate=False)
    changed = changed_latest or changed_full
    if changed:
        await _persist_workflow_plan(message_repo, session_id, plan)
    return plan, changed


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
    user_content: str | None = None,
) -> dict | None:
    from src.agent.policy_context import latest_user_line

    latest = (user_content or latest_user_line(session_text) or "").strip()

    existing = await get_workflow_plan_from_session(message_repo, session_id)
    if existing is None:
        plan = build_initial_workflow_plan(session_text)
        if plan is None:
            return metadata
        meta = dict(metadata or {})
        meta[_PLAN_META_KEY] = plan
        return meta

    plan, _changed = await sync_workflow_plan_with_message(
        message_repo, session_id, latest
    )
    plan = await get_workflow_plan_from_session(message_repo, session_id) or plan
    if plan is None or len(plan.get("nodes") or []) < 2:
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
    if booking.get("status") in ("submitted", "completed"):
        return True
    progress = booking.get("booking_progress")
    if isinstance(progress, dict) and progress.get("needs_return"):
        if (
            progress.get("outbound") == "completed"
            and progress.get("return") == "completed"
        ):
            return True
    return False


async def set_booking_leg_progress(
    message_repo,
    session_id: str,
    *,
    leg: str,
    status: str,
    needs_return: bool,
    outbound_selection: dict | None = None,
) -> dict[str, Any] | None:
    plan = await get_workflow_plan_from_session(message_repo, session_id)
    if plan is None:
        return None
    node = _node_by_id(plan, "booking")
    if node is None:
        return plan
    progress = dict(node.get("booking_progress") or {})
    progress["needs_return"] = needs_return
    progress[leg] = status
    node["booking_progress"] = progress
    if outbound_selection is not None:
        node["outbound_selection"] = outbound_selection
    await _persist_workflow_plan(message_repo, session_id, plan)
    return plan


def get_outbound_selection_from_plan(wf_plan: dict | None) -> dict | None:
    if not wf_plan:
        return None
    node = _node_by_id(wf_plan, "booking")
    if not node:
        return None
    raw = node.get("outbound_selection")
    return dict(raw) if isinstance(raw, dict) else None


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


_FINISHED_NODE_STATUSES = ("submitted", "completed", "cancelled")
_CONFIRM_ACTION_TEXT = re.compile(r"^确认开始办理|^确认并开始")


def _is_confirm_action_text(text: str) -> bool:
    return bool(_CONFIRM_ACTION_TEXT.search((text or "").strip()))


def _node_awaiting_confirm(plan: dict[str, Any], node: dict[str, Any]) -> bool:
    """尚未完成信息确认的节点才可作为自动推进的下一站。"""
    if node.get("id") == "hotel" and not _booking_gate_open(plan):
        return False
    if node.get("status") in _FINISHED_NODE_STATUSES:
        return False
    if node.get("task_id"):
        return False
    return node.get("status") in ("pending", "running", None)


def _advance_active_node(
    plan: dict[str, Any],
    *,
    after_node_id: str | None = None,
) -> None:
    """将焦点推进到「刚完成节点之后」的下一个待确认节点，不回头选已办节点。"""
    ordered = _nodes_in_display_order(plan)
    start = 0
    if after_node_id:
        for idx, node in enumerate(ordered):
            if node.get("id") == after_node_id:
                start = idx + 1
                break

    search = ordered[start:]
    for node in search:
        if _node_awaiting_confirm(plan, node) and node.get("status") == "pending":
            node["status"] = "running"
            plan["active_node_id"] = node.get("id")
            return
    for node in search:
        if _node_awaiting_confirm(plan, node) and node.get("status") == "running":
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
    if node is None:
        _advance_active_node(plan)
        _enforce_booking_before_hotel(plan)
        return
    if node.get("status") in _FINISHED_NODE_STATUSES:
        _advance_active_node(plan, after_node_id=str(active_id))
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


async def mark_plan_node_cancelled(
    message_repo,
    session_id: str,
    node_id: str,
    *,
    task_id: str | None = None,
) -> dict[str, Any] | None:
    """将指定流程节点置为已取消（不依赖 task 匹配）。"""
    if not node_id:
        return await get_workflow_plan_from_session(message_repo, session_id)

    plan = await get_workflow_plan_from_session(message_repo, session_id)
    if plan is None:
        return None

    node = _node_by_id(plan, node_id)
    if node is None:
        return plan

    changed = False
    if task_id and not node.get("task_id"):
        node["task_id"] = task_id
        changed = True
    if node.get("status") != "cancelled":
        node["status"] = "cancelled"
        changed = True
    if plan.get("active_node_id") == node_id:
        _advance_active_node(plan, after_node_id=node_id)
        changed = True

    _normalize_plan_nodes(plan)
    if _enforce_booking_before_hotel(plan):
        changed = True

    if changed:
        await _persist_workflow_plan(message_repo, session_id, plan)
    return plan


async def update_plan_for_task(
    message_repo,
    session_id: str,
    task_id: str,
    status: str,
    *,
    task_steps: list[dict] | None = None,
    node_id: str | None = None,
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
    if node_id:
        node = _node_by_id(plan, node_id)
        if node is not None:
            if task_id and not node.get("task_id"):
                node["task_id"] = task_id
                changed = True
            matched = [node]

    if not matched:
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("task_id") == task_id:
                matched.append(node)

    if not matched and task_steps:
        category = infer_category(task_steps)
        inferred_node_id = _TASK_CATEGORY_TO_NODE.get(category)
        if inferred_node_id:
            node = _node_by_id(plan, inferred_node_id)
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
        submitted_id = next(
            (str(node.get("id")) for node in matched if node.get("id")),
            None,
        )
        _prepare_parallel_after_submit(plan, after_node_id=submitted_id)
        changed = True

    if status == "cancelled":
        cancelled_ids = {node.get("id") for node in matched}
        if plan.get("active_node_id") in cancelled_ids:
            _advance_active_node(
                plan,
                after_node_id=str(plan.get("active_node_id") or ""),
            )
            changed = True

    if status == "running" and any(
        node.get("status") == "running" for node in matched
    ):
        plan["active_node_id"] = matched[0].get("id")
        changed = True

    if status == "completed":
        prev_active = plan.get("active_node_id")
        matched_active = any(
            plan.get("active_node_id") == node.get("id") for node in matched
        )
        if matched_active:
            _advance_active_node(plan, after_node_id=str(prev_active or ""))
        else:
            active = _node_by_id(plan, plan.get("active_node_id") or "")
            if active and active.get("status") == "completed":
                _advance_active_node(
                    plan,
                    after_node_id=str(plan.get("active_node_id") or ""),
                )
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
        plan = meeting_plan_for_node(build_meeting_plan(user_messages), node_id)
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


_SUMMARY_REQUEST_PATTERN = re.compile(
    r"结果汇总|办理结果(?:汇总|详情)?|复制汇总|导出汇总|(?:请|给我)?(?:看看)?汇总(?:结果|一下)?",
    re.I,
)


def is_session_summary_request(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    return bool(_SUMMARY_REQUEST_PATTERN.search(stripped))


async def try_session_summary_reply(
    message_repo,
    session_id: str,
    user_content: str,
) -> tuple[str, str, dict | None] | None:
    """用户主动索要办理结果汇总时，返回可复制面板，不走各业务工作流。"""
    if not is_session_summary_request(user_content):
        return None

    plan = await get_workflow_plan_from_session(message_repo, session_id)
    if not plan:
        return (
            "当前会话还没有多节点办理计划。请先说明要办理的事项，例如：「出差订机票订酒店并开国能会议」。",
            "text",
            None,
        )

    copy_text = await build_session_results_summary(message_repo, session_id, plan)
    nodes = plan.get("nodes")
    completed_labels = [
        str(node.get("label"))
        for node in nodes
        if isinstance(node, dict) and node.get("status") == "completed"
    ] if isinstance(nodes, list) else []

    if completed_labels:
        summary_label = "、".join(label for label in completed_labels if label)
        content = "\n".join(
            [
                "**办理结果汇总**",
                "",
                f"已完成：{summary_label}。",
                "",
                "以下为可复制内容：",
            ]
        )
    else:
        content = "\n".join(
            [
                "**办理结果汇总**",
                "",
                "当前还没有已完成的办理节点；完成 OA 办理后再来查看即可复制保存。",
                "",
                "以下为当前可汇总内容：",
            ]
        )

    return content, "text", {
        "workflow_plan": plan,
        "workflow_session_summary": {"text": copy_text},
    }


async def build_session_results_summary(
    message_repo,
    session_id: str,
    plan: dict[str, Any],
) -> str:
    records = await message_repo.list_recent_for_context(session_id, limit=80)
    task_meta: dict[str, dict[str, Any]] = {}
    for record in records:
        meta = record.metadata_json or {}
        tid = meta.get("task_id")
        if not tid:
            continue
        merged = task_meta.setdefault(str(tid), {})
        for key, value in meta.items():
            if value is not None and value is not False:
                merged[key] = value

    lines = ["【办理详情】"]
    detail_count = 0

    for node in _nodes_in_display_order(plan):
        if node.get("status") != "completed":
            continue
        node_id = str(node.get("id") or "")
        label = str(node.get("label") or _LABELS.get(node_id, node_id))
        task_id = str(node.get("task_id") or "")
        meta = task_meta.get(task_id, {}) if task_id else {}
        if not meta:
            meta = _find_meta_for_node(node_id, task_meta)
        meta = _enrich_node_meta_from_records(node_id, meta, records, task_id)

        detail_count += 1
        lines.append(f"  {detail_count}. {label}")
        lines.extend(_format_node_result_lines(node_id, meta))
        lines.append("")

    if detail_count == 0:
        lines.append("  （暂无已完成节点）")

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def _detail_line(key: str, value: str | None) -> str:
    text = str(value or "").strip()
    return f"     {key}：{text or '—'}"


def _format_datetime_display(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text[:16] if len(text) > 16 else text


def _format_date_display(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return _format_datetime_display(text)


def _find_meta_for_node(node_id: str, task_meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result_keys = {
        "gn_meeting": "gn_meeting_result",
        "email": "email_sent_result",
        "room": "room_booking_result",
        "travel": "travel_apply_result",
        "booking": "transport_booking_result",
        "hotel": "hotel_booking_result",
        "workpackage": "workpackage_result",
        "leave": "leave_result",
    }
    key = result_keys.get(node_id)
    if not key:
        return {}
    for meta in task_meta.values():
        value = meta.get(key)
        if value:
            return meta
    return {}


def _transport_booking_from_selection(selection: dict) -> dict[str, str] | None:
    is_train = selection.get("transport_type") == "train"
    mode = "高铁" if is_train else "机票"
    origin = str(selection.get("origin") or "—")
    destination = str(selection.get("destination") or "—")
    options = selection.get("trains") if is_train else selection.get("flights")
    if not isinstance(options, list) or not options:
        return {
            "transport_mode": mode,
            "origin": origin,
            "destination": destination,
            "flight_no": "—",
            "departure_date": "—",
            "departure_time": "—",
        }
    picked = options[0] if isinstance(options[0], dict) else None
    if not picked:
        return None
    dep_time = str(picked.get("departure_time") or "")
    dep_date = dep_time.split(" ")[0] if dep_time else "—"
    dep_clock = dep_time.split(" ")[1] if " " in dep_time else "—"
    ticket_no = str(picked.get("train_no") or picked.get("flight_no") or "—")
    return {
        "transport_mode": mode,
        "origin": str(picked.get("origin") or origin),
        "destination": str(picked.get("destination") or destination),
        "flight_no": ticket_no,
        "departure_date": dep_date,
        "departure_time": dep_clock,
    }


def _transport_mode_from_travel_confirm(record_meta: dict) -> str | None:
    confirm = record_meta.get("travel_plan_confirm")
    if not isinstance(confirm, dict) or confirm.get("email_only"):
        return None
    raw = str(confirm.get("transport_mode") or "").strip()
    mapping = {"飞机": "机票", "火车": "高铁", "自驾": "自驾", "其他": "—"}
    return mapping.get(raw, raw or None)


def _hotel_booking_from_selection(selection: dict) -> dict[str, str] | None:
    hotels = selection.get("hotels")
    if not isinstance(hotels, list) or not hotels:
        return None
    hotel = hotels[0] if isinstance(hotels[0], dict) else None
    if not hotel:
        return None
    amount = hotel.get("price_per_night")
    return {
        "hotel_name": str(hotel.get("name") or "—"),
        "room_type": str(hotel.get("room_type") or "—"),
        "amount": str(amount) if amount is not None else "—",
        "check_in": str(hotel.get("check_in") or "—"),
        "check_out": str(hotel.get("check_out") or "—"),
    }


def _enrich_node_meta_from_records(
    node_id: str,
    meta: dict[str, Any],
    records,
    task_id: str,
) -> dict[str, Any]:
    enriched = dict(meta)

    if node_id == "booking":
        existing = enriched.get("transport_booking_result")
        if isinstance(existing, dict):
            has_route = str(existing.get("origin") or "").strip() not in ("", "—")
            has_mode = str(existing.get("transport_mode") or "").strip() not in ("", "—")
            if has_route and has_mode:
                return enriched

        for record in reversed(records):
            record_meta = record.metadata_json or {}
            if task_id and record_meta.get("task_id") == task_id:
                tb = record_meta.get("transport_booking_result")
                if isinstance(tb, dict):
                    enriched["transport_booking_result"] = tb
                    return enriched

        for record in reversed(records):
            record_meta = record.metadata_json or {}
            tb = record_meta.get("transport_booking_result")
            if isinstance(tb, dict) and str(tb.get("origin") or tb.get("flight_no") or "").strip() not in ("", "—"):
                enriched["transport_booking_result"] = tb
                return enriched

        for record in reversed(records):
            record_meta = record.metadata_json or {}
            selection = record_meta.get("booking_selection")
            if not isinstance(selection, dict):
                continue
            if selection.get("booking_kind") not in (None, "transport") and not selection.get("needs_flight"):
                continue
            picked = _transport_booking_from_selection(selection)
            if picked:
                mode = _transport_mode_from_travel_confirm(record_meta)
                if mode and mode != "—":
                    picked["transport_mode"] = mode
                enriched["transport_booking_result"] = picked
                return enriched

        for record in reversed(records):
            record_meta = record.metadata_json or {}
            confirm = record_meta.get("travel_plan_confirm")
            if not isinstance(confirm, dict) or confirm.get("email_only"):
                continue
            mode = _transport_mode_from_travel_confirm(record_meta)
            origin = str(confirm.get("origin") or "—")
            destination = str(confirm.get("destination") or "—")
            if mode or origin != "—" or destination != "—":
                enriched["transport_booking_result"] = {
                    "transport_mode": mode or "—",
                    "origin": origin,
                    "destination": destination,
                    "flight_no": "—",
                    "departure_date": str(confirm.get("start_date") or "—"),
                    "departure_time": "—",
                }
                return enriched

        return enriched

    if node_id != "hotel":
        return enriched

    existing = enriched.get("hotel_booking_result")
    if isinstance(existing, dict) and str(existing.get("hotel_name") or "").strip() not in ("", "—"):
        return enriched

    for record in reversed(records):
        record_meta = record.metadata_json or {}
        if task_id and record_meta.get("task_id") == task_id:
            hb = record_meta.get("hotel_booking_result")
            if isinstance(hb, dict):
                enriched["hotel_booking_result"] = hb
                return enriched

    for record in reversed(records):
        record_meta = record.metadata_json or {}
        hb = record_meta.get("hotel_booking_result")
        if isinstance(hb, dict) and str(hb.get("hotel_name") or "").strip() not in ("", "—"):
            enriched["hotel_booking_result"] = hb
            return enriched

    for record in reversed(records):
        record_meta = record.metadata_json or {}
        selection = record_meta.get("booking_selection")
        if not isinstance(selection, dict):
            continue
        if selection.get("booking_kind") not in (None, "hotel") and not selection.get("needs_hotel"):
            continue
        picked = _hotel_booking_from_selection(selection)
        if picked:
            enriched["hotel_booking_result"] = picked
            return enriched

    return enriched


def _format_node_result_lines(node_id: str, meta: dict[str, Any]) -> list[str]:
    if node_id == "gn_meeting":
        gn = meta.get("gn_meeting_result")
        if not isinstance(gn, dict):
            return [_detail_line("状态", "已创建")]
        return [
            _detail_line("主题", str(gn.get("subject") or meta.get("task_title") or "—")),
            _detail_line("会议链接", str(gn.get("meeting_link") or "—")),
            _detail_line("会议密码", str(gn.get("meeting_password") or "—")),
        ]

    if node_id == "email":
        em = meta.get("email_sent_result")
        if not isinstance(em, dict):
            return [_detail_line("状态", "已发送")]
        return [
            _detail_line("邮件标题", str(em.get("subject") or "—")),
            _detail_line("发送时间", _format_datetime_display(str(em.get("sent_at") or ""))),
            _detail_line("主要内容梗概", str(em.get("body_summary") or "—")),
        ]

    if node_id == "room":
        room = meta.get("room_booking_result")
        if not isinstance(room, dict):
            return [_detail_line("状态", "已预约")]
        return [
            _detail_line("会议室", str(room.get("room_name") or "—")),
            _detail_line("主题", str(room.get("subject") or "—")),
            _detail_line("时间", f"{room.get('start_time') or '—'} — {room.get('end_time') or '—'}"),
            _detail_line("参会人", str(room.get("attendees") or "—")),
        ]

    if node_id == "travel":
        tr = meta.get("travel_apply_result")
        if not isinstance(tr, dict):
            return [_detail_line("状态", "已审批通过")]
        return [
            _detail_line("差旅单号", str(tr.get("receipt_id") or "—")),
            _detail_line("开始时间", _format_date_display(str(tr.get("departure_date") or ""))),
            _detail_line("结束时间", _format_date_display(str(tr.get("return_date") or ""))),
        ]

    if node_id == "booking":
        tb = meta.get("transport_booking_result")
        if not isinstance(tb, dict):
            return [_detail_line("状态", "已预定")]
        dep_date = _format_date_display(str(tb.get("departure_date") or ""))
        dep_time = str(tb.get("departure_time") or "").strip()
        depart_at = f"{dep_date} {dep_time}".strip() if dep_time and dep_time != "—" else dep_date
        return [
            _detail_line("交通方式", str(tb.get("transport_mode") or "—")),
            _detail_line("出发地", str(tb.get("origin") or "—")),
            _detail_line("目的地", str(tb.get("destination") or "—")),
            _detail_line("班次", str(tb.get("flight_no") or "—")),
            _detail_line("发车时间", depart_at),
        ]

    if node_id == "hotel":
        hb = meta.get("hotel_booking_result")
        if not isinstance(hb, dict):
            return [_detail_line("状态", "已预定")]
        amount = str(hb.get("amount") or "").strip()
        amount_label = f"{amount} 元/晚" if amount and amount != "—" else "—"
        return [
            _detail_line("酒店名称", str(hb.get("hotel_name") or "—")),
            _detail_line("房型", str(hb.get("room_type") or "—")),
            _detail_line("单价", amount_label),
            _detail_line("入住日期", _format_date_display(str(hb.get("check_in") or ""))),
            _detail_line("离店日期", _format_date_display(str(hb.get("check_out") or ""))),
        ]

    if node_id == "workpackage":
        wp = meta.get("workpackage_result")
        if not isinstance(wp, dict):
            return [_detail_line("状态", "已提交")]
        return [
            _detail_line("项目", str(wp.get("project") or "—")),
            _detail_line("填报周期", str(wp.get("period") or "—")),
            _detail_line("工时", f"{wp.get('hours') or '—'} 小时"),
            _detail_line("工作内容", str(wp.get("content") or "—")),
            _detail_line("回执单号", str(wp.get("receipt_id") or "—")),
        ]

    if node_id == "leave":
        lv = meta.get("leave_result")
        if not isinstance(lv, dict):
            return [_detail_line("状态", "已审批通过")]
        return [
            _detail_line("请假类型", str(lv.get("leave_type") or "—")),
            _detail_line("开始日期", str(lv.get("date_start") or "—")),
            _detail_line("结束日期", str(lv.get("date_end") or "—")),
            _detail_line("天数", str(lv.get("days") or "—")),
            _detail_line("事由", str(lv.get("reason") or "—")),
            _detail_line("回执单号", str(lv.get("receipt_id") or "—")),
        ]

    if node_id == "info_collect":
        return [_detail_line("状态", "已发布")]

    title = str(meta.get("task_title") or "—")
    category = str(meta.get("category") or "")
    return [
        _detail_line("事项", title),
        _detail_line("类型", category or "综合办事"),
        _detail_line("状态", "已完成"),
    ]


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
    meeting_plan = None
    if active_id in ("room", "gn_meeting"):
        synced = sync_meeting_plan_with_workflow_nodes(
            build_meeting_plan(ctx.user_messages), plan
        )
        meeting_plan = meeting_plan_for_node(synced, active_id)
    submitted_labels = [
        str(item.get("label") or "")
        for item in nodes
        if isinstance(item, dict) and item.get("status") == "submitted"
    ]

    lines = [
        "**接下来请办理：**" + label,
        "",
        "已根据对话内容自查并预填，请核对下方确认卡片，可直接修改后确认。",
        "",
    ]
    if submitted_labels:
        waiting = "、".join(label for label in submitted_labels if label)
        lines.append(f"「{waiting}」信息已确认，您可并行准备本节点信息。")
        lines.append("")
    leave_plan = build_leave_plan(ctx.user_messages) if active_id == "leave" else None

    if missing:
        lines.append(f"还需要您补充：**{'、'.join(missing)}**")
        lines.append("")
        if active_id in ("room", "gn_meeting") and meeting_plan and can_present_meeting_confirm(meeting_plan):
            lines.append("会议信息已从对话中识别，请在下方卡片中核对主题、时间与参会人员并确认。")
        elif active_id == "leave" and leave_plan is not None:
            lines.append("请假信息已从对话中识别，请在下方卡片中核对日期、时段与事由并确认。")
        else:
            lines.append(_NODE_GUIDANCE.get(active_id, "请补充相关信息后继续办理。"))
    else:
        if active_id in ("room", "gn_meeting") and meeting_plan and can_present_meeting_confirm(meeting_plan):
            lines.append("会议信息已从对话中识别，请在下方卡片中核对主题、时间与参会人员并确认。")
        elif active_id == "leave" and leave_plan is not None:
            lines.append("请假信息已从对话中识别，请在下方卡片中核对并确认。")
        else:
            lines.append("相关信息已从对话中识别，您可以直接说「开始办理」或补充细节后继续。")
        hint = _NODE_GUIDANCE.get(active_id)
        if hint and not (
            active_id in ("room", "gn_meeting")
            and meeting_plan
            and can_present_meeting_confirm(meeting_plan)
        ) and active_id != "leave":
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

    next_node_meta: dict[str, Any] = {
        "node_id": active_id,
        "label": label,
        "missing_slots": missing,
    }
    if active_id == "booking":
        travel_plan = build_travel_plan(ctx.user_messages)
        combined = merge_user_texts(
            [
                record.content.strip()
                for record in ctx.user_messages
                if getattr(record, "role", None) == "user" and record.content.strip()
            ]
        )
        next_node_meta["origin"] = travel_plan.origin or ""
        next_node_meta["destination"] = travel_plan.destination or ""
        next_node_meta["transport_type"] = resolve_transport_booking_type(combined, travel_plan)

    metadata: dict[str, Any] = {
        "workflow_next_node": next_node_meta,
        "workflow_plan": plan,
    }
    if active_id == "leave" and leave_plan is not None:
        metadata.update(build_leave_plan_confirm_metadata(leave_plan))
        next_node_meta["missing_slots"] = []
    elif (
        active_id in ("room", "gn_meeting")
        and meeting_plan is not None
        and can_present_meeting_confirm(meeting_plan)
    ):
        metadata.update(
            build_meeting_plan_confirm_metadata(
                meeting_plan, confirm_node_id=active_id
            )
        )
        next_node_meta["missing_slots"] = []
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
