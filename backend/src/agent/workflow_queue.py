"""多意图工作流编排：识别、分段与顺序推进。"""

from __future__ import annotations

import re

from src.agent.leave_workflow import is_leave_workflow_intent as _is_leave_intent_on_segment
from src.agent.workpackage_workflow import is_workpackage_workflow_intent as _is_wp_intent_on_segment

_SEGMENT_SPLIT = re.compile(r"(?:此外|另外|还有|并且|同时|以及|然后|再帮|还要|还想)")
_WORKFLOW_ORDER = ("workpackage", "leave", "meeting", "travel")
_WORKFLOW_LABELS = {
    "workpackage": "填报工时",
    "leave": "申请请假",
    "meeting": "预约会议",
    "travel": "申请出差",
}
_QUEUE_META_KEY = "workflow_queue"


def split_intent_segments(text: str) -> list[str]:
    parts = [p.strip() for p in _SEGMENT_SPLIT.split(text) if p.strip()]
    return parts if len(parts) > 1 else [text.strip()]


def detect_workflow_intents(text: str) -> list[str]:
    segments = split_intent_segments(text)
    found: list[str] = []
    for workflow in _WORKFLOW_ORDER:
        for segment in segments:
            if workflow == "workpackage" and _is_wp_intent_on_segment(segment):
                found.append(workflow)
                break
            if workflow == "leave" and _is_leave_intent_on_segment(segment):
                found.append(workflow)
                break
    return found


def multi_intent_preamble(intents: list[str]) -> str:
    if len(intents) <= 1:
        return ""
    labels = [_WORKFLOW_LABELS[i] for i in intents if i in _WORKFLOW_LABELS]
    if len(labels) < 2:
        return ""
    joined = "和".join(labels)
    first = _WORKFLOW_LABELS.get(intents[0], labels[0])
    second = _WORKFLOW_LABELS.get(intents[1], labels[1])
    return f"我们识别出您想要{joined}，我们先做{first}，再{second}。"


def attach_workflow_queue(metadata: dict | None, intents: list[str], active: str) -> dict:
    meta = dict(metadata or {})
    remaining = [i for i in intents if i != active and i in _WORKFLOW_ORDER]
    if remaining:
        meta[_QUEUE_META_KEY] = remaining
    elif _QUEUE_META_KEY in meta:
        meta.pop(_QUEUE_META_KEY, None)
    return meta


async def get_pending_workflow_queue(message_repo, session_id: str) -> list[str]:
    records = await message_repo.list_recent_for_context(session_id, limit=30)
    for record in reversed(records):
        if record.role != "assistant":
            continue
        meta = record.metadata_json or {}
        queue = meta.get(_QUEUE_META_KEY)
        if isinstance(queue, list) and queue:
            return [str(item) for item in queue]
    return []


def consume_workflow_queue(metadata: dict | None, completed: str) -> dict:
    meta = dict(metadata or {})
    queue = meta.get(_QUEUE_META_KEY)
    if not isinstance(queue, list):
        return meta
    remaining = [item for item in queue if str(item) != completed]
    if remaining:
        meta[_QUEUE_META_KEY] = remaining
    else:
        meta.pop(_QUEUE_META_KEY, None)
    return meta
