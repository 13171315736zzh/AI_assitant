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


async def supersede_pending_interactive_metas(
    message_repo, session_id: str, keys: list[str]
) -> bool:
    """将最近助手消息里仍为 pending 的交互卡片标记为 superseded。"""
    messages = await message_repo.list_recent_for_context(session_id, limit=24)
    changed = False
    for record in reversed(messages):
        if record.role != "assistant":
            continue
        meta = dict(record.metadata_json or {})
        record_changed = False
        for key in keys:
            item = meta.get(key)
            if not isinstance(item, dict) or item.get("status") != "pending":
                continue
            item = dict(item)
            item["status"] = "superseded"
            meta[key] = item
            record_changed = True
        if record_changed:
            record.metadata_json = meta
            changed = True
    return changed


async def try_reopen_confirmed_plan(
    message_repo,
    session_id: str,
    key: str,
    user_content: str,
    *,
    is_update,
    can_present,
    build_content,
    build_metadata,
    plan,
    pending_plan_msg=None,
    has_pending_plan_flag: bool = False,
    supersede_keys: list[str] | None = None,
) -> tuple[str, str, dict] | None:
    """用户已确认 plan 后又提出修改 → 重新下发可编辑确认卡。"""
    if not await is_meta_confirmed(message_repo, session_id, key):
        return None
    if not is_update(user_content):
        return None
    if pending_plan_msg and has_pending_plan_flag:
        mark_meta_superseded(pending_plan_msg, key)
    if supersede_keys:
        await supersede_pending_interactive_metas(message_repo, session_id, supersede_keys)
    if not can_present(plan):
        return None
    return build_content(plan, updated=True), "text", build_metadata(plan)
