from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import re

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.task_catalog import build_task_summary, category_label, infer_category
from src.agent.workflow_plan import (
    append_next_node_guidance,
    build_next_node_guidance,
    update_plan_for_task,
)
from src.models.session import MessagePublic
from src.models.task import (
    OaTaskActionPublic,
    TaskConfirmPublic,
    TaskPublic,
    TaskStatusPublic,
    TaskStepPublic,
    TaskSummaryPublic,
)
from src.repositories.form import FormRepository
from src.repositories.session import MessageRepository, SessionRepository
from src.repositories.task import TaskRepository
from src.services.form import FormService
from src.integrations.mock_meeting_provider import generate_gn_meeting_credentials

_APPLY_TOOLS = (
    "workpackage_fill",
    "leave_apply",
    "travel_apply",
    "meeting_book",
    "gn_meeting_book",
    "flight_book",
    "hotel_book",
)

_COMPLETION_COPY = {
    "workpackage": {
        "title": "工时填报",
        "chain": "项目经理 → 部门负责人 → 工时审核岗",
    },
    "leave": {
        "title": "请假申请",
        "chain": "直属主管 → 部门负责人 → 人事审核",
    },
    "travel": {
        "title": "差旅申请",
        "chain": "部门负责人 → 分管领导 → 行政审批",
    },
    "meeting": {
        "title": "会议室预约",
        "chain": "行政审核 → 会议室管理岗",
    },
    "gn_meeting": {
        "title": "国能会议",
        "chain": "会议组织岗 → 部门负责人 → IT 支持岗",
    },
    "transport_book": {
        "title": "交通预订",
        "chain": "行政审批 → 出票确认",
    },
    "hotel_book": {
        "title": "酒店预订",
        "chain": "行政审批 → 预订确认",
    },
}


def _to_task_public(record) -> TaskPublic:
    steps = [TaskStepPublic(**step) for step in (record.steps_json or [])]
    return TaskPublic(
        id=record.id,
        session_id=record.session_id,
        goal=record.goal,
        status=record.status,
        current_step=record.current_step,
        total_steps=record.total_steps,
        replan_count=record.replan_count,
        steps=steps,
        created_at=record.created_at.isoformat(),
    )


def _to_message_public(record) -> MessagePublic:
    return MessagePublic(
        id=record.id,
        session_id=record.session_id,
        role=record.role,
        content=record.content,
        message_type=record.message_type,
        metadata=record.metadata_json,
        created_at=record.created_at.isoformat(),
    )


def _find_apply_step(steps: list[dict]) -> dict | None:
    for step in steps:
        if step.get("tool") in _APPLY_TOOLS:
            return step
    return None


def _find_user_confirm_step(steps: list[dict]) -> dict | None:
    for step in steps:
        if step.get("tool") == "user_confirm":
            return step
    return None


def _form_id_from_step(step: dict | None) -> str | None:
    if not step:
        return None
    result = step.get("result") or {}
    form_id = result.get("form_id")
    return str(form_id) if form_id else None


async def _sync_related_task_cards(
    message_repo,
    session_id: str,
    task_id: str,
    task_record,
    steps_desc: str,
) -> None:
    records = await message_repo.list_recent_for_context(session_id, limit=40)
    total = task_record.total_steps or len(task_record.steps_json or []) or 2
    for record in records:
        meta = dict(record.metadata_json or {})
        related = meta.get("related_tasks")
        if not isinstance(related, list):
            continue
        changed = False
        for item in related:
            if not isinstance(item, dict) or item.get("task_id") != task_id:
                continue
            item["progress"] = f"{total}/{total}"
            item["progress_percent"] = 100
            base = str(item.get("steps_desc") or steps_desc).split(" · ")[0]
            item["steps_desc"] = f"{base} · 已完成"
            changed = True
        if changed:
            meta["related_tasks"] = related
            await message_repo.update(record, metadata_json=meta)
            return


def _build_completion_content(category: str, task_title: str, receipt_id: str | None) -> str:
    copy = _COMPLETION_COPY.get(category, {"title": "业务办理", "chain": "相关审批节点"})
    receipt_line = f"\n- 回执单号：**{receipt_id}**" if receipt_id else ""
    if category == "gn_meeting":
        return "\n".join(
            [
                f"✅ **{task_title or copy['title']}已创建**",
                "",
                "会议已在国能会议系统中创建成功，请在下方卡片中复制会议链接与密码。",
                receipt_line,
            ]
        )
    if category == "meeting":
        return "\n".join(
            [
                f"✅ **{task_title or copy['title']}已完成**",
                "",
                f"OA 审批已通过（{copy['chain']}）。预约详情见下方卡片。{receipt_line}",
            ]
        )
    if category == "transport_book":
        return "\n".join(
            [
                f"✅ **{task_title or copy['title']}已预定**",
                "",
                f"交通预订已完成，票务信息已同步至智能办公助手。{receipt_line}",
            ]
        )
    if category == "hotel_book":
        return "\n".join(
            [
                f"✅ **{task_title or copy['title']}已预定**",
                "",
                f"酒店预订已完成，入住信息已同步至智能办公助手。{receipt_line}",
            ]
        )
    return "\n".join(
        [
            f"✅ **{task_title or copy['title']}已完成**",
            "",
            f"OA 审批已通过（{copy['chain']}），办理结果已同步至智能办公助手。{receipt_line}",
            "",
            "您可在「我的任务」中查看详情，或继续在本对话中办理其他事项。",
        ]
    )


def _field_str(fields: dict | None, key: str, default: str = "—") -> str:
    value = (fields or {}).get(key)
    text = str(value).strip() if value is not None else ""
    return text or default


def _infer_transport_mode(
    steps: list[dict], form_fields: dict | None, result: dict | None
) -> str:
    fields = form_fields or {}
    pref = _field_str(fields, "transport_mode")
    if pref not in ("—", ""):
        return pref

    selected: dict = {}
    if isinstance(result, dict):
        raw_selected = result.get("selected")
        if isinstance(raw_selected, dict):
            selected = raw_selected
        if selected.get("train_no") or result.get("train_no"):
            return "高铁"
        if selected.get("flight_no"):
            return "机票"

    ticket = _field_str(fields, "flight_no")
    if ticket != "—":
        if re.match(r"^[GDCZK]\d", ticket, re.I):
            return "高铁"
        return "机票"
    return "—"


def _extract_transport_booking_result(
    steps: list[dict], form_fields: dict | None, receipt_id: str | None = None
) -> dict[str, str]:
    apply_step = next((s for s in steps if s.get("tool") == "flight_book"), None)
    result = (apply_step or {}).get("result") or {}
    fields = form_fields or {}
    flight_no = _field_str(fields, "flight_no")
    if flight_no == "—" and isinstance(result, dict):
        flight_no = _field_str(result, "train_no")
    return {
        "transport_mode": _infer_transport_mode(steps, form_fields, result if isinstance(result, dict) else None),
        "origin": _field_str(fields, "origin"),
        "destination": _field_str(fields, "destination"),
        "passenger_name": _field_str(fields, "passenger_name"),
        "departure_date": _field_str(fields, "departure_date"),
        "departure_time": _field_str(fields, "departure_time"),
        "flight_no": flight_no,
        "amount": _field_str(fields, "amount"),
        "receipt_id": receipt_id or "—",
    }


def _extract_hotel_booking_result(
    form_fields: dict | None, receipt_id: str | None = None
) -> dict[str, str]:
    fields = form_fields or {}
    return {
        "guest_name": _field_str(fields, "guest_name"),
        "hotel_name": _field_str(fields, "hotel_name"),
        "room_type": _field_str(fields, "room_type"),
        "check_in": _field_str(fields, "check_in"),
        "check_out": _field_str(fields, "check_out"),
        "amount": _field_str(fields, "amount"),
        "receipt_id": receipt_id or "—",
    }


def _extract_travel_apply_result(
    form_fields: dict | None, receipt_id: str | None = None
) -> dict[str, str]:
    fields = form_fields or {}
    return {
        "destination": _field_str(fields, "destination"),
        "departure_date": _field_str(fields, "departure_date"),
        "return_date": _field_str(fields, "return_date"),
        "project": _field_str(fields, "project"),
        "transport": _field_str(fields, "transport"),
        "description": _field_str(fields, "description"),
        "receipt_id": receipt_id or "—",
    }


def _extract_workpackage_result(
    form_fields: dict | None, receipt_id: str | None = None
) -> dict[str, str]:
    fields = form_fields or {}
    return {
        "project": _field_str(fields, "project"),
        "period": _field_str(fields, "period"),
        "hours": _field_str(fields, "hours"),
        "content": _field_str(fields, "content"),
        "receipt_id": receipt_id or "—",
    }


def _extract_leave_result(
    form_fields: dict | None, receipt_id: str | None = None
) -> dict[str, str]:
    fields = form_fields or {}
    return {
        "leave_type": _field_str(fields, "leave_type"),
        "date_start": _field_str(fields, "date_start"),
        "date_end": _field_str(fields, "date_end"),
        "days": _field_str(fields, "days"),
        "reason": _field_str(fields, "reason"),
        "receipt_id": receipt_id or "—",
    }


def _extract_room_booking_result(steps: list[dict], form_fields: dict | None) -> dict[str, str]:
    room_step = next((s for s in steps if s.get("tool") == "room_book"), None)
    room_raw = ""
    if room_step:
        room_raw = str((room_step.get("result") or {}).get("room") or "")
    fields = form_fields or {}
    room_name = str(fields.get("room") or room_raw or "—")
    if room_raw and "会议室" not in room_name:
        room_name = f"{room_raw} 会议室"
    time_label = str((room_step or {}).get("params", {}).get("time") or "")
    start_time = str(fields.get("start_time") or time_label or "—")
    end_time = str(fields.get("end_time") or "—")
    return {
        "room_name": room_name,
        "subject": str(fields.get("subject") or "—"),
        "start_time": start_time,
        "end_time": end_time,
        "time_label": time_label or start_time,
        "attendees": str(fields.get("attendees") or "—"),
    }


def _form_id_from_email_step(steps: list[dict]) -> str | None:
    for step in steps:
        if step.get("tool") == "email_notify":
            return _form_id_from_step(step)
    return None


def _summarize_email_body(body: str | None, max_len: int = 96) -> str:
    if not body:
        return "—"
    text = re.sub(r"\s+", " ", str(body).strip())
    for marker in ("此致", "敬礼", "Best regards", "Regards", "顺祝"):
        idx = text.find(marker)
        if idx > 24:
            text = text[:idx].strip()
            break
    if len(text) <= max_len:
        return text or "—"
    return text[: max_len - 1].rstrip() + "…"


async def _build_completion_payload(
    service: "TaskService",
    user_id: int,
    record,
    steps: list[dict],
    category: str,
    task_title: str,
    receipt_id: str | None,
) -> tuple[str, dict[str, Any]]:
    completion_content = _build_completion_content(category, task_title, receipt_id)
    assistant_metadata: dict[str, Any] = {
        "oa_completion": True,
        "task_id": record.id,
        "category": category,
    }

    apply_step = _find_apply_step(steps)
    form_id = _form_id_from_step(apply_step)
    form_fields: dict | None = None
    if form_id:
        form_record = await service.form_repo.get_by_id(form_id, user_id)
        if form_record and form_record.fields_json:
            form_fields = dict(form_record.fields_json)

    if category == "gn_meeting":
        subject = (form_fields or {}).get("subject") if form_fields else task_title
        credentials = generate_gn_meeting_credentials(record.id, str(subject or ""))
        if apply_step is not None:
            apply_step["result"] = {
                **(apply_step.get("result") or {}),
                **credentials,
            }
        assistant_metadata["gn_meeting_result"] = credentials
    elif category == "meeting":
        booking = _extract_room_booking_result(steps, form_fields)
        assistant_metadata["room_booking_result"] = booking
    elif category == "transport_book":
        assistant_metadata["transport_booking_result"] = _extract_transport_booking_result(
            steps, form_fields, receipt_id
        )
    elif category == "hotel_book":
        assistant_metadata["hotel_booking_result"] = _extract_hotel_booking_result(
            form_fields, receipt_id
        )
    elif category == "travel":
        assistant_metadata["travel_apply_result"] = _extract_travel_apply_result(
            form_fields, receipt_id
        )
    elif category == "workpackage":
        assistant_metadata["workpackage_result"] = _extract_workpackage_result(
            form_fields, receipt_id
        )
    elif category == "leave":
        assistant_metadata["leave_result"] = _extract_leave_result(form_fields, receipt_id)

    if task_title:
        assistant_metadata["task_title"] = task_title

    return completion_content, assistant_metadata


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_repo = TaskRepository(db)
        self.form_repo = FormRepository(db)
        self.message_repo = MessageRepository(db)
        self.session_repo = SessionRepository(db)
        self.form_service = FormService(self.form_repo)

    async def list_tasks(
        self,
        user_id: int,
        page: int,
        page_size: int,
        status: str | None = None,
        category: str | None = None,
    ) -> tuple[list[TaskSummaryPublic], int]:
        records = await self.task_repo.list_all_by_user(user_id)
        summaries = [TaskSummaryPublic(**build_task_summary(r)) for r in records]

        if status == "running":
            summaries = [s for s in summaries if s.status == "running"]
        elif status == "completed":
            summaries = [s for s in summaries if s.status == "completed"]
        elif status == "cancelled":
            summaries = [s for s in summaries if s.status == "cancelled"]
        else:
            summaries = [s for s in summaries if s.status != "cancelled"]

        if category:
            summaries = [s for s in summaries if s.category == category]

        total = len(summaries)
        start = (page - 1) * page_size
        return summaries[start : start + page_size], total

    async def get_task(self, user_id: int, task_id: str) -> TaskPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None:
            return None
        return _to_task_public(record)

    async def cancel_task(self, user_id: int, task_id: str) -> TaskStatusPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None:
            return None
        if record.status in ("completed", "cancelled"):
            return TaskStatusPublic(id=record.id, status=record.status)
        updated = await self.task_repo.update(record, status="cancelled")
        return TaskStatusPublic(id=updated.id, status=updated.status)

    async def confirm_task(
        self, user_id: int, task_id: str, step_id: int, params: dict | None = None
    ) -> TaskConfirmPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None:
            return None
        if record.status == "cancelled":
            return None

        steps = list(record.steps_json or [])
        for step in steps:
            if step.get("step_id") == step_id:
                if params:
                    step["params"] = {**step.get("params", {}), **params}
                step["status"] = "running"
                break

        updated = await self.task_repo.update(
            record,
            status="running",
            current_step=step_id,
            steps_json=steps,
        )
        return TaskConfirmPublic(
            id=updated.id,
            status=updated.status,
            current_step=updated.current_step,
        )

    async def update_step_params(
        self, user_id: int, task_id: str, step_id: int, params: dict
    ) -> TaskPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None:
            return None

        steps = list(record.steps_json or [])
        found = False
        for step in steps:
            if step.get("step_id") == step_id:
                step["params"] = {**step.get("params", {}), **params}
                found = True
                break
        if not found:
            return None

        updated = await self.task_repo.update(record, steps_json=steps)
        return _to_task_public(updated)

    async def _ensure_form_submitted(
        self, user_id: int, task_record, steps: list[dict]
    ) -> tuple[str | None, str | None]:
        apply_step = _find_apply_step(steps)
        form_id = _form_id_from_step(apply_step)
        if not form_id:
            return None, None

        form_record = await self.form_repo.get_by_id(form_id, user_id)
        if form_record is None:
            return None, None

        if form_record.status != "submitted":
            submit_result = await self.form_service.submit(
                user_id, form_id, dict(form_record.fields_json or {})
            )
            if submit_result is None:
                return form_id, None
            receipt_id = submit_result.receipt_id
            if apply_step is not None:
                apply_step["result"] = {
                    **(apply_step.get("result") or {}),
                    "receipt_id": receipt_id,
                    "form_id": form_id,
                }
            return form_id, receipt_id

        return form_id, form_record.receipt_id

    async def submit_oa_application(
        self, user_id: int, task_id: str
    ) -> OaTaskActionPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None or record.status == "cancelled":
            return None

        steps = list(record.steps_json or [])
        form_id, receipt_id = await self._ensure_form_submitted(user_id, record, steps)
        if not form_id:
            return None

        now = datetime.now(UTC).isoformat()
        confirm_step = _find_user_confirm_step(steps)
        if confirm_step is not None:
            confirm_step["status"] = "running"
            confirm_step["result"] = {
                **(confirm_step.get("result") or {}),
                "oa_submitted": True,
                "submitted_at": now,
                "receipt_id": receipt_id,
                "form_id": form_id,
            }

        updated = await self.task_repo.update(
            record,
            status="running",
            steps_json=steps,
            current_step=confirm_step["step_id"] if confirm_step else record.current_step,
        )
        updated_plan = await update_plan_for_task(
            self.message_repo, updated.session_id, task_id, "submitted", task_steps=steps
        )
        assistant_record = None
        if updated_plan:
            guidance, guidance_meta = await build_next_node_guidance(
                self.message_repo, updated.session_id, updated_plan
            )
            if guidance.strip():
                assistant_record = await self.message_repo.create(
                    updated.session_id,
                    "assistant",
                    guidance,
                    "text",
                    metadata=guidance_meta,
                )
                session_record = await self.session_repo.get_by_id(
                    updated.session_id, user_id
                )
                if session_record is not None:
                    session_record.message_count += 1
                    await self.session_repo.update(session_record)
        assistant_message = (
            _to_message_public(assistant_record).model_dump()
            if assistant_record is not None
            else None
        )
        return OaTaskActionPublic(
            task=_to_task_public(updated),
            session_id=updated.session_id,
            receipt_id=receipt_id,
            assistant_message=assistant_message,
        )

    async def approve_oa_application(
        self, user_id: int, task_id: str
    ) -> OaTaskActionPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None or record.status == "cancelled":
            return None

        steps = list(record.steps_json or [])
        category = infer_category(steps)
        form_id, receipt_id = await self._ensure_form_submitted(user_id, record, steps)
        if not form_id:
            return None

        now = datetime.now(UTC).isoformat()
        for step in steps:
            step["status"] = "completed"
            if step.get("tool") == "user_confirm":
                step["result"] = {
                    **(step.get("result") or {}),
                    "oa_submitted": True,
                    "oa_approved": True,
                    "approved_at": now,
                    "receipt_id": receipt_id,
                    "form_id": form_id,
                    "approval_chain": _COMPLETION_COPY.get(category, {}).get("chain", ""),
                }

        task_message = await self.message_repo.find_task_message(
            record.session_id, record.id
        )
        task_title = record.goal[:40]
        steps_desc = category_label(category)
        if task_message and task_message.metadata_json:
            meta = dict(task_message.metadata_json)
            task_title = str(meta.get("task_title") or task_title)
            steps_desc = str(meta.get("steps_desc") or steps_desc)

        completion_content, assistant_metadata = await _build_completion_payload(
            self,
            user_id,
            record,
            steps,
            category,
            task_title,
            receipt_id,
        )

        updated = await self.task_repo.update(
            record,
            status="completed",
            current_step=record.total_steps,
            steps_json=steps,
        )

        if task_message and task_message.metadata_json:
            meta = dict(task_message.metadata_json)
            total = updated.total_steps or len(steps) or 2
            meta.update(
                {
                    "progress": f"{total}/{total}",
                    "progress_percent": 100,
                    "status": "completed",
                    "steps_desc": f"{steps_desc} · 已完成",
                }
            )
            for result_key in (
                "hotel_booking_result",
                "transport_booking_result",
                "travel_apply_result",
                "room_booking_result",
                "gn_meeting_result",
                "workpackage_result",
                "leave_result",
            ):
                if assistant_metadata.get(result_key):
                    meta[result_key] = assistant_metadata[result_key]
            await self.message_repo.update(task_message, metadata_json=meta)

        await _sync_related_task_cards(
            self.message_repo,
            updated.session_id,
            task_id,
            updated,
            steps_desc,
        )

        updated_plan = await update_plan_for_task(
            self.message_repo, updated.session_id, task_id, "completed", task_steps=steps
        )

        if updated_plan:
            guidance, guidance_meta = await build_next_node_guidance(
                self.message_repo, updated.session_id, updated_plan
            )
            completion_content = append_next_node_guidance(completion_content, guidance)
            if guidance_meta:
                assistant_metadata.update(guidance_meta)

        assistant_record = await self.message_repo.create(
            updated.session_id,
            "assistant",
            completion_content,
            "text",
            metadata=assistant_metadata,
        )

        session_record = await self.session_repo.get_by_id(
            updated.session_id, user_id
        )
        if session_record is not None:
            session_record.message_count += 1
            await self.session_repo.update(session_record)

        return OaTaskActionPublic(
            task=_to_task_public(updated),
            session_id=updated.session_id,
            receipt_id=receipt_id,
            assistant_message=_to_message_public(assistant_record).model_dump(),
        )

    async def create_gn_meeting(
        self, user_id: int, task_id: str
    ) -> OaTaskActionPublic | None:
        """国能会议：用户确认后直接创建，无需 OA 审批流程。"""
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None or record.status == "cancelled":
            return None
        category = infer_category(record.steps_json or [])
        if category != "gn_meeting":
            return None
        if record.status == "completed":
            recent = await self.message_repo.list_recent_for_context(
                record.session_id, limit=12
            )
            assistant_msg = None
            for msg in reversed(recent):
                meta = msg.metadata_json or {}
                if meta.get("gn_meeting_result") and meta.get("task_id") == task_id:
                    assistant_msg = _to_message_public(msg).model_dump()
                    break
            return OaTaskActionPublic(
                task=_to_task_public(record),
                session_id=record.session_id,
                assistant_message=assistant_msg,
            )
        return await self.approve_oa_application(user_id, task_id)

    async def create_transport_booking(
        self, user_id: int, task_id: str
    ) -> OaTaskActionPublic | None:
        """交通预订：用户确认后直接预定，无需 OA 审批流程。"""
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None or record.status == "cancelled":
            return None
        category = infer_category(record.steps_json or [])
        if category != "transport_book":
            return None
        if record.status == "completed":
            recent = await self.message_repo.list_recent_for_context(
                record.session_id, limit=12
            )
            assistant_msg = None
            for msg in reversed(recent):
                meta = msg.metadata_json or {}
                if meta.get("oa_completion") and meta.get("task_id") == task_id:
                    assistant_msg = _to_message_public(msg).model_dump()
                    break
            return OaTaskActionPublic(
                task=_to_task_public(record),
                session_id=record.session_id,
                assistant_message=assistant_msg,
            )
        return await self.approve_oa_application(user_id, task_id)

    async def create_hotel_booking(
        self, user_id: int, task_id: str
    ) -> OaTaskActionPublic | None:
        """酒店预订：用户确认后直接预定，无需 OA 审批流程。"""
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None or record.status == "cancelled":
            return None
        category = infer_category(record.steps_json or [])
        if category != "hotel_book":
            return None
        if record.status == "completed":
            recent = await self.message_repo.list_recent_for_context(
                record.session_id, limit=12
            )
            assistant_msg = None
            for msg in reversed(recent):
                meta = msg.metadata_json or {}
                if meta.get("oa_completion") and meta.get("task_id") == task_id:
                    assistant_msg = _to_message_public(msg).model_dump()
                    break
            return OaTaskActionPublic(
                task=_to_task_public(record),
                session_id=record.session_id,
                assistant_message=assistant_msg,
            )
        return await self.approve_oa_application(user_id, task_id)

    async def confirm_email_sent(
        self,
        user_id: int,
        task_id: str,
        *,
        recipient: str | None = None,
        subject: str | None = None,
        message_id: str | None = None,
        body: str | None = None,
        sent_at: str | None = None,
    ) -> OaTaskActionPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None or record.status == "cancelled":
            return None

        steps = deepcopy(record.steps_json or [])
        if not any(step.get("tool") == "email_notify" for step in steps):
            return None

        if record.status == "completed":
            assistant_msg = None
            recent = await self.message_repo.list_recent_for_context(
                record.session_id, limit=8
            )
            for msg in reversed(recent):
                meta = msg.metadata_json or {}
                if meta.get("email_sent_result") and meta.get("task_id") == task_id:
                    assistant_msg = _to_message_public(msg).model_dump()
                    break
            return OaTaskActionPublic(
                task=_to_task_public(record),
                session_id=record.session_id,
                assistant_message=assistant_msg,
            )

        now = datetime.now(UTC).isoformat()
        sent_time = (sent_at or "").strip() or now
        email_body = (body or "").strip()
        if not email_body:
            form_id = _form_id_from_email_step(steps)
            if form_id:
                form_record = await self.form_repo.get_by_id(form_id, user_id)
                if form_record and form_record.fields_json:
                    email_body = str(form_record.fields_json.get("body") or "").strip()

        sent_payload = {
            "email_sent": True,
            "sent_at": sent_time,
            "message_id": message_id,
            "recipient": recipient,
            "subject": subject,
            "body": email_body,
        }

        for step in steps:
            if step.get("tool") == "email_notify":
                step["status"] = "completed"
                step["result"] = {**(step.get("result") or {}), **sent_payload}
            elif step.get("tool") == "user_confirm":
                step["status"] = "completed"
                step["result"] = dict(sent_payload)

        task_message = await self.message_repo.find_task_message(
            record.session_id, record.id
        )
        task_title = record.goal[:40]
        if task_message and task_message.metadata_json:
            meta = dict(task_message.metadata_json)
            task_title = str(meta.get("task_title") or task_title)

        recipient_label = (recipient or "").strip() or "收件人"
        subject_label = (subject or "").strip() or task_title
        completion_content = "\n".join(
            [
                "✅ **邮件已发送成功**",
                "",
                f"- 收件人：{recipient_label}",
                f"- 主题：{subject_label}",
                "",
                "写邮件流程已全部完成（2/2）。您可在邮件「已发送」中查看或撤回（演示）。",
            ]
        )
        assistant_metadata: dict[str, Any] = {
            "email_sent_result": {
                "recipient": recipient_label,
                "subject": subject_label,
                "message_id": message_id,
                "sent_at": sent_time,
                "body_summary": _summarize_email_body(email_body),
            },
            "task_id": record.id,
            "category": "email",
        }

        total_steps = record.total_steps or len(steps) or 2
        updated = await self.task_repo.update(
            record,
            status="completed",
            current_step=total_steps,
            steps_json=steps,
        )

        if task_message and task_message.metadata_json:
            meta = dict(task_message.metadata_json)
            meta.update(
                {
                    "progress": f"{total_steps}/{total_steps}",
                    "progress_percent": 100,
                    "status": "completed",
                    "steps_desc": "邮件撰写 · 已完成",
                }
            )
            await self.message_repo.update(task_message, metadata_json=meta)

        updated_plan = await update_plan_for_task(
            self.message_repo,
            updated.session_id,
            task_id,
            "completed",
            task_steps=steps,
        )
        if updated_plan:
            guidance, guidance_meta = await build_next_node_guidance(
                self.message_repo, updated.session_id, updated_plan
            )
            completion_content = append_next_node_guidance(completion_content, guidance)
            if guidance_meta:
                assistant_metadata.update(guidance_meta)

        assistant_record = await self.message_repo.create(
            updated.session_id,
            "assistant",
            completion_content,
            "text",
            metadata=assistant_metadata,
        )

        session_record = await self.session_repo.get_by_id(
            updated.session_id, user_id
        )
        if session_record is not None:
            session_record.message_count += 1
            await self.session_repo.update(session_record)

        return OaTaskActionPublic(
            task=_to_task_public(updated),
            session_id=updated.session_id,
            assistant_message=_to_message_public(assistant_record).model_dump(),
        )
