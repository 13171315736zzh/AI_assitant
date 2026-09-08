"""工作流交互确认：槽位补全后的 plan confirm 通用辅助。"""

from __future__ import annotations


def _travel_plan_item(meta: dict | None) -> dict | None:
    if not meta:
        return None
    item = meta.get("travel_plan_confirm")
    if not item or item.get("email_only"):
        return None
    return item


async def get_pending_meta(message_repo, session_id: str, key: str):
    messages = await message_repo.list_recent_for_context(session_id, limit=12)
    for record in reversed(messages):
        if record.role != "assistant":
            continue
        meta = record.metadata_json or {}
        item = meta.get(key)
        if item and item.get("status") == "pending":
            return record, item
    return None, None


async def get_pending_travel_plan_meta(message_repo, session_id: str):
    """差旅单确认（排除 email_only 邮件确认卡）。"""
    messages = await message_repo.list_recent_for_context(session_id, limit=12)
    for record in reversed(messages):
        if record.role != "assistant":
            continue
        item = _travel_plan_item(record.metadata_json or {})
        if item and item.get("status") == "pending":
            return record, item
    return None, None


async def is_meta_confirmed(message_repo, session_id: str, key: str) -> bool:
    messages = await message_repo.list_recent_for_context(session_id, limit=20)
    for record in reversed(messages):
        if record.role != "assistant":
            continue
        meta = record.metadata_json or {}
        item = meta.get(key)
        if item:
            return item.get("status") == "confirmed"
    return False


async def is_travel_plan_confirmed(message_repo, session_id: str) -> bool:
    """差旅单是否已确认（不受邮件撰写确认影响）。"""
    messages = await message_repo.list_recent_for_context(session_id, limit=30)
    for record in reversed(messages):
        if record.role != "assistant":
            continue
        item = _travel_plan_item(record.metadata_json or {})
        if not item:
            continue
        status = item.get("status")
        if status == "confirmed":
            return True
        if status == "pending":
            return False
    return False


def mark_meta_confirmed(message_record, key: str) -> None:
    meta = dict(message_record.metadata_json or {})
    item = dict(meta.get(key) or {})
    item["status"] = "confirmed"
    meta[key] = item
    message_record.metadata_json = meta


def mark_meta_superseded(message_record, key: str) -> None:
    meta = dict(message_record.metadata_json or {})
    item = dict(meta.get(key) or {})
    if item.get("status") != "pending":
        return
    item["status"] = "superseded"
    meta[key] = item
    message_record.metadata_json = meta
