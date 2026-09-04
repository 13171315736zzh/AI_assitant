"""单会话上下文：合并用户发言、去重当前轮、供各工作流与 Agent 统一读取。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import SimpleNamespace

DEFAULT_CONTEXT_LIMIT = 40

_PLAN_REVISION_PATTERN = re.compile(
    r"改|换|调整|补充|更新|更正|不对|不是|换个|改成|再说|还有|另外|补充一下"
)


@dataclass
class SessionContext:
    records: list
    user_messages: list
    user_texts: list[str]
    merged_text: str
    combined_text: str
    latest_user_text: str


def merge_user_texts(texts: list[str]) -> str:
    return "\n".join(text.strip() for text in texts if text and text.strip())


def append_current_user_turn(records, user_content: str | None) -> list:
    """若当前轮尚未落库，追加到消息列表；已落库则去重（修复 stream 路径重复）。"""
    messages = list(records)
    trimmed = (user_content or "").strip()
    if not trimmed:
        return messages
    last_user = ""
    for record in reversed(messages):
        if getattr(record, "role", None) == "user":
            last_user = record.content.strip()
            break
    if last_user != trimmed:
        messages.append(SimpleNamespace(role="user", content=trimmed))
    return messages


async def load_session_context(
    message_repo,
    session_id: str,
    *,
    user_content: str | None = None,
    limit: int = DEFAULT_CONTEXT_LIMIT,
) -> SessionContext:
    records = await message_repo.list_recent_for_context(session_id, limit=limit)
    user_messages = append_current_user_turn(records, user_content)
    user_texts = [
        message.content.strip()
        for message in user_messages
        if getattr(message, "role", None) == "user" and message.content.strip()
    ]
    merged_text = merge_user_texts(user_texts)
    combined_text = " ".join(user_texts)
    latest_user_text = user_texts[-1] if user_texts else (user_content or "").strip()
    return SessionContext(
        records=records,
        user_messages=user_messages,
        user_texts=user_texts,
        merged_text=merged_text,
        combined_text=combined_text,
        latest_user_text=latest_user_text,
    )


def is_plan_revision_text(text: str) -> bool:
    return bool(_PLAN_REVISION_PATTERN.search(text.strip()))


def has_pending_plan(pending: dict | None) -> bool:
    return bool(pending and pending.get("status") == "pending")


def extend_user_messages(user_messages: list, supplementary: str | None) -> list:
    """将输入框尚未发送的补充说明临时并入上下文（确认/合并卡片时用）。"""
    text = (supplementary or "").strip()
    if not text:
        return user_messages
    return [*user_messages, SimpleNamespace(role="user", content=text)]
