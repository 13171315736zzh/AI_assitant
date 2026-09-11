"""多节点办理计划：节点完成后推进与下一节点确认引导。"""

from __future__ import annotations

from typing import Any

from src.agent.workflow_plan import (
    _LABELS,
    _advance_active_node,
    _node_by_id,
    _persist_workflow_plan,
    append_next_node_guidance,
    build_next_node_guidance,
    get_workflow_plan_from_session,
)

_OA_ENTRY_LABELS: dict[str, str] = {
    "gn_meeting": "前往 OA 提交国能会议",
    "room": "前往 OA 提交会议室预约",
    "leave": "前往 OA 提交请假申请",
    "travel": "前往 OA 提交差旅申请",
    "workpackage": "前往 OA 提交工时填报",
    "booking": "前往 OA 预订车票",
    "hotel": "前往 OA 预订酒店",
    "email": "打开邮件确认发送",
}


def build_completed_node_snapshot(
    node_id: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    meta = dict(metadata or {})
    items = meta.get("confirmed_items")
    if not isinstance(items, list):
        items = []
    normalized = [
        {"label": str(item.get("label") or ""), "value": str(item.get("value") or "—")}
        for item in items
        if isinstance(item, dict)
    ]
    if node_id == "gn_meeting":
        normalized = [
            item for item in normalized if item["label"] not in ("会议室", "会议室偏好", "人数要求")
        ]
    return {
        "node_id": node_id,
        "node_label": _LABELS.get(node_id, node_id),
        "task_id": meta.get("task_id"),
        "task_title": meta.get("task_title"),
        "steps_desc": meta.get("steps_desc"),
        "progress": meta.get("progress"),
        "progress_percent": meta.get("progress_percent"),
        "meeting_kind": meta.get("meeting_kind"),
        "booking_kind": meta.get("booking_kind"),
        "items": normalized,
        "oa_label": _OA_ENTRY_LABELS.get(node_id, "前往 OA 继续办理"),
    }


async def advance_workflow_node_after_confirm(
    message_repo,
    session_id: str,
    node_id: str,
) -> dict[str, Any] | None:
    """将当前节点标记为已提交，并激活下一个待办节点。"""
    plan = await get_workflow_plan_from_session(message_repo, session_id)
    if plan is None:
        return None
    node = _node_by_id(plan, node_id)
    if node and node.get("status") not in ("completed", "cancelled"):
        node["status"] = "submitted"
    _advance_active_node(plan, after_node_id=node_id)
    await _persist_workflow_plan(message_repo, session_id, plan)
    return plan


def is_intermediate_workflow_result(metadata: dict[str, Any] | None) -> bool:
    """中间态交互（如会议室点选、返程订票）不推进到下一办理节点。"""
    if not metadata:
        return False
    if metadata.get("room_selection"):
        return True
    booking = metadata.get("booking_selection")
    if isinstance(booking, dict) and booking.get("status") not in (
        "confirmed",
        "superseded",
    ):
        return True
    workpackage_fill = metadata.get("workpackage_confirm")
    if isinstance(workpackage_fill, dict) and workpackage_fill.get("status") == "pending":
        return True
    return False


async def append_workflow_guidance_after_node(
    message_repo,
    session_id: str,
    node_id: str,
    result: tuple[str, str, dict],
) -> tuple[str, str, dict]:
    """节点确认并创建任务后，自查下一节点并附带确认引导。"""
    if is_intermediate_workflow_result(result[2]):
        return result

    updated_plan = await advance_workflow_node_after_confirm(
        message_repo, session_id, node_id
    )
    if updated_plan is None:
        return result

    guidance, guidance_meta = await build_next_node_guidance(
        message_repo, session_id, updated_plan
    )
    metadata = dict(result[2] or {})
    metadata["workflow_completed_node"] = build_completed_node_snapshot(node_id, metadata)
    if guidance.strip():
        content = append_next_node_guidance(result[0], guidance)
        if guidance_meta:
            metadata.update(guidance_meta)
        return content, result[1], metadata
    return result[0], result[1], metadata
