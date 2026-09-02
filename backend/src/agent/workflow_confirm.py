"""工作流交互确认：槽位补全后的 plan confirm 通用辅助。"""

from __future__ import annotations


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


def mark_meta_confirmed(message_record, key: str) -> None:
    meta = dict(message_record.metadata_json or {})
    item = dict(meta.get(key) or {})
    item["status"] = "confirmed"
    meta[key] = item
    message_record.metadata_json = meta
