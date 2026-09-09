"""工作流节点取消：意图识别与确认卡片元数据。"""

from __future__ import annotations

import re
from typing import Any

from src.agent.meeting_workflow import is_room_cancel_intent
from src.agent.travel_workflow import is_booking_cancel_intent, resolve_booking_cancel_node
from src.agent.workflow_plan import _LABELS, _node_by_id, match_node_from_text

CANCEL_META_KEY = "workflow_cancel_confirm"
MEETING_CANCEL_SELECTION_META_KEY = "meeting_cancel_selection"

_CANCEL_VERB = re.compile(r"取消|退订|撤销|作废|不要(?:了)?")
_MEETING_GENERIC = re.compile(r"会议|开会")

_NODE_CANCEL_TARGETS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("room", re.compile(r"会议室|会议预约|会议预定|线下会议", re.I)),
    ("hotel", re.compile(r"酒店|住宿|订房|入住")),
    ("booking", re.compile(r"车票|机票|交通|航班|火车|高铁|订票")),
    ("gn_meeting", re.compile(r"国能会|国能会议|线上会议|视频会议")),
    ("travel", re.compile(r"差旅|出差|差旅单")),
    ("workpackage", re.compile(r"工时|工包")),
    ("leave", re.compile(r"请假|休假|补假")),
    ("email", re.compile(r"邮件|发信|写信")),
    ("info_collect", re.compile(r"填信息|信息收集|信息采集|个人信息|长期记忆")),
)

_SNAPSHOT_ITEM_LABELS: dict[str, tuple[tuple[str, str], ...]] = {
    "travel": (
        ("OA工单号", "receipt_id"),
        ("目的地", "destination"),
        ("出发日期", "departure_date"),
        ("返回日期", "return_date"),
        ("项目", "project"),
        ("交通方式", "transport"),
        ("事由", "description"),
    ),
    "booking": (
        ("交通方式", "transport_mode"),
        ("出发地", "origin"),
        ("目的地", "destination"),
        ("乘车人", "passenger_name"),
        ("出发日期", "departure_date"),
        ("出发时间", "departure_time"),
        ("车次/航班", "flight_no"),
    ),
    "hotel": (
        ("入住人", "guest_name"),
        ("酒店", "hotel_name"),
        ("房型", "room_type"),
        ("入住", "check_in"),
        ("离店", "check_out"),
    ),
    "workpackage": (
        ("项目", "project"),
        ("周期", "period"),
        ("工时", "hours"),
        ("工作内容", "content"),
    ),
    "leave": (
        ("OA工单号", "receipt_id"),
        ("类型", "leave_type"),
        ("开始", "date_start"),
        ("结束", "date_end"),
        ("天数", "days"),
        ("事由", "reason"),
    ),
    "room": (
        ("会议室", "room_name"),
        ("会议主题", "subject"),
        ("会议时间", "time_label"),
        ("参会人员", "attendees"),
    ),
    "gn_meeting": (
        ("会议主题", "subject"),
        ("会议时间", "time_label"),
        ("参会人员", "attendees"),
        ("会议号", "meeting_no"),
        ("会议密码", "meeting_password"),
    ),
    "email": (
        ("收件人", "recipient"),
        ("主题", "subject"),
        ("正文摘要", "body_summary"),
    ),
    "info_collect": (
        ("姓名", "name"),
        ("工号", "employee_id"),
        ("部门", "department"),
        ("Base", "base_location"),
    ),
}


def node_label(node_id: str) -> str:
    return _LABELS.get(node_id, node_id)


def is_meeting_cancel_selection_intent(
    text: str, wf_plan: dict[str, Any] | None = None
) -> bool:
    """取消会议但未明确国能会/会议室时，需先让用户多选。"""
    stripped = (text or "").strip()
    if not stripped or not _CANCEL_VERB.search(stripped):
        return False
    if is_room_cancel_intent(stripped):
        return False
    if re.search(r"国能会|国能会议|线上会议|视频会议", stripped):
        return False
    return bool(_MEETING_GENERIC.search(stripped))


def resolve_workflow_cancel_node(text: str, wf_plan: dict[str, Any] | None) -> str | None:
    """识别用户要取消的流程节点。"""
    stripped = (text or "").strip()
    if not stripped:
        return None

    if is_meeting_cancel_selection_intent(stripped, wf_plan):
        return None

    if is_room_cancel_intent(stripped):
        return "room"

    booking_node = resolve_booking_cancel_node(stripped)
    if booking_node:
        return booking_node

    if not _CANCEL_VERB.search(stripped):
        return None

    for node_id, pattern in _NODE_CANCEL_TARGETS:
        if pattern.search(stripped):
            return node_id

    matched = match_node_from_text(stripped)
    if matched and _CANCEL_VERB.search(stripped):
        return matched

    if wf_plan:
        active_id = wf_plan.get("active_node_id")
        active = _node_by_id(wf_plan, active_id) if active_id else None
        if active and active.get("status") in ("running", "submitted"):
            return str(active_id)

    return None


def is_workflow_cancel_intent(text: str, wf_plan: dict[str, Any] | None = None) -> bool:
    if is_meeting_cancel_selection_intent(text, wf_plan):
        return False
    return resolve_workflow_cancel_node(text, wf_plan) is not None


def build_meeting_cancel_selection_content() -> str:
    return "请选择要取消的会议类型，确认后将进入取消确认。"


def build_meeting_cancel_selection_metadata(
    options: list[dict[str, str | bool]],
) -> dict:
    return {
        "interactive": True,
        MEETING_CANCEL_SELECTION_META_KEY: {
            "status": "pending",
            "title": "选择取消的会议",
            "confirm_label": "确认选择",
            "options": options,
        },
    }


def snapshot_to_items(node_id: str, snapshot: dict[str, str]) -> list[dict[str, str]]:
    mapping = _SNAPSHOT_ITEM_LABELS.get(node_id, ())
    items: list[dict[str, str]] = []
    for label, key in mapping:
        value = str(snapshot.get(key) or "").strip()
        if not value or value == "—":
            continue
        if key == "time_label":
            end_time = str(snapshot.get("end_time") or "").strip()
            if (
                end_time
                and end_time != "—"
                and end_time not in value
            ):
                value = f"{value} — {end_time}"
        items.append({"label": label, "value": value})
    if items:
        return items
    fallback = str(snapshot.get("summary") or snapshot.get("task_title") or "").strip()
    if fallback and fallback != "—":
        return [{"label": "办理内容", "value": fallback}]
    return [{"label": "办理项", "value": node_label(node_id)}]


def build_cancel_confirm_content(node_label_text: str) -> str:
    return f"请确认是否取消以下{node_label_text}："


def build_cancel_confirm_metadata(
    *,
    node_id: str,
    node_label_text: str,
    task_id: str,
    items: list[dict[str, str]],
    cancel_queue: list[dict[str, str]] | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "status": "pending",
        "title": f"确认取消{node_label_text}",
        "confirm_label": "确认取消",
        "node_id": node_id,
        "node_label": node_label_text,
        "task_id": task_id,
        "items": items,
    }
    if cancel_queue:
        payload["cancel_queue"] = cancel_queue
    return {
        "interactive": True,
        CANCEL_META_KEY: payload,
    }
