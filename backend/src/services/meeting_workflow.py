"""会议预约流程执行。"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.meeting_workflow import (
    MeetingPlan,
    build_execution_summary,
    build_meeting_plan,
    build_meeting_plan_confirm_content,
    build_meeting_plan_confirm_metadata,
    build_room_selection_content,
    build_room_selection_metadata,
    build_task_metadata,
    is_meeting_workflow_intent,
    is_ready_to_execute,
)
from src.agent.workflow_confirm import get_pending_meta, is_meta_confirmed, mark_meta_confirmed
from src.db.task_models import TaskRecord
from src.integrations.mock_meeting_provider import query_room_availability
from src.repositories.form import FormRepository
from src.repositories.session import MessageRepository
from src.repositories.task import TaskRepository
from src.repositories.user import UserRepository
from src.services.form import FormService


def _new_task_id() -> str:
    return f"task_{secrets.token_hex(4)}"


class MeetingWorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.task_repo = TaskRepository(db)
        self.form_repo = FormRepository(db)
        self.user_repo = UserRepository(db)
        self.form_service = FormService(self.form_repo)

    async def try_execute(
        self,
        user_id: int,
        session_id: str,
        user_content: str,
    ) -> tuple[str, str, dict] | None:
        history = await self.message_repo.list_recent_for_context(session_id, limit=40)
        from types import SimpleNamespace

        full_history = list(history) + [SimpleNamespace(role="user", content=user_content)]
        combined = " ".join(m.content for m in full_history if m.role == "user")
        if not is_meeting_workflow_intent(combined):
            return None

        plan = build_meeting_plan(full_history)
        if not is_ready_to_execute(plan):
            return None

        pending_plan_msg, pending_plan = await get_pending_meta(
            self.message_repo, session_id, "meeting_plan_confirm"
        )
        if pending_plan_msg and pending_plan:
            return (
                "👇 请核对会议信息并点击「确认开始办理」。",
                "text",
                {"interactive": True, "meeting_plan_confirm": pending_plan},
            )

        plan_confirmed = await is_meta_confirmed(
            self.message_repo, session_id, "meeting_plan_confirm"
        )

        pending_msg, pending_sel = await self._get_pending_room_selection(session_id)
        if plan_confirmed and pending_msg and pending_sel:
            return (
                "👇 请在下方勾选可用会议室，完成后点击「确认预约」。",
                "text",
                {"interactive": True, "room_selection": pending_sel},
            )

        if not plan_confirmed:
            content = build_meeting_plan_confirm_content(plan)
            metadata = build_meeting_plan_confirm_metadata(plan)
            return content, "text", metadata

        availability = await query_room_availability(
            plan.room or "236",
            date_hint=plan.date_hint,
            start_hint=plan.start_hint,
            end_hint=plan.end_hint,
        )
        pub = availability.to_public_dict()

        if not pub["available"]:
            content = build_room_selection_content(plan, pub)
            metadata = build_room_selection_metadata(plan, pub)
            return content, "text", metadata

        return await self._create_task_reply(user_id, session_id, plan, pub["requested_room"], pub)

    async def confirm_meeting_plan(
        self,
        user_id: int,
        session_id: str,
    ) -> tuple[str, str, dict] | None:
        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, "meeting_plan_confirm"
        )
        if pending_msg is None or pending is None:
            return None

        history = await self.message_repo.list_recent_for_context(session_id, limit=40)
        plan = build_meeting_plan(history)
        if not is_ready_to_execute(plan):
            return None

        mark_meta_confirmed(pending_msg, "meeting_plan_confirm")
        await self.db.flush()

        availability = await query_room_availability(
            plan.room or "236",
            date_hint=plan.date_hint,
            start_hint=plan.start_hint,
            end_hint=plan.end_hint,
        )
        pub = availability.to_public_dict()

        if not pub["available"]:
            content = build_room_selection_content(plan, pub)
            metadata = build_room_selection_metadata(plan, pub)
            return content, "text", metadata

        return await self._create_task_reply(
            user_id, session_id, plan, pub["requested_room"], pub
        )

    async def confirm_room_selection(
        self,
        user_id: int,
        session_id: str,
        room: str,
    ) -> tuple[str, str, dict] | None:
        pending_msg, pending = await self._get_pending_room_selection(session_id)
        if pending_msg is None or pending is None:
            return None

        options = pending.get("options") or []
        if not any(o.get("room") == room for o in options):
            return None

        history = await self.message_repo.list_recent_for_context(session_id, limit=40)
        plan = build_meeting_plan(history)
        if not is_ready_to_execute(plan):
            return None

        await self._mark_selection_confirmed(pending_msg, "room_selection")

        availability = {
            "requested_room": room,
            "time_label": pending.get("time_label", ""),
            "start_time": pending.get("start_time", ""),
            "end_time": pending.get("end_time", ""),
        }
        return await self._create_task_reply(user_id, session_id, plan, room, availability)

    async def _create_task_reply(
        self,
        user_id: int,
        session_id: str,
        plan: MeetingPlan,
        room: str,
        availability: dict,
    ) -> tuple[str, str, dict]:
        task_id = _new_task_id()
        time_label = availability.get("time_label", "")
        steps = [
            {
                "step_id": 1,
                "action": "会议室确认",
                "tool": "room_book",
                "status": "completed",
                "depends_on": [],
                "params": {"room": room, "time": time_label},
                "result": {"room": room, "status": "confirmed"},
            },
            {
                "step_id": 2,
                "action": "会议预约",
                "tool": "meeting_book",
                "status": "running",
                "depends_on": [1],
                "params": {"subject": plan.subject or ""},
                "result": None,
            },
            {
                "step_id": 3,
                "action": "用户确认",
                "tool": "user_confirm",
                "status": "pending",
                "depends_on": [2],
                "params": {},
                "result": None,
            },
        ]

        task = TaskRecord(
            id=task_id,
            session_id=session_id,
            user_id=user_id,
            goal=plan.raw_goal[:500] or f"{plan.subject}预约",
            status="running",
            current_step=1,
            total_steps=3,
            replan_count=0,
            steps_json=steps,
            created_at=datetime.now(UTC),
        )
        await self.task_repo.create(task)

        meeting_form = await self.form_service.preview(
            user_id,
            "meeting",
            session_id,
            task_id,
            {
                "subject": plan.subject or "工作会议",
                "start_time": availability.get("start_time", ""),
                "end_time": availability.get("end_time", ""),
                "room": f"{room} 会议室",
                "attendees": plan.attendees or "待定",
            },
        )
        if meeting_form:
            for step in steps:
                if step["tool"] == "meeting_book":
                    step["status"] = "completed"
                    step["result"] = {"form_id": meeting_form.form_id}

        await self.task_repo.update(task, steps_json=steps, current_step=2)

        content = build_execution_summary(plan, task_id, room, time_label)
        metadata = build_task_metadata(plan, task_id)
        return content, "task", metadata

    async def _get_pending_room_selection(self, session_id: str):
        messages = await self.message_repo.list_recent_for_context(session_id, limit=12)
        for record in reversed(messages):
            if record.role != "assistant":
                continue
            meta = record.metadata_json or {}
            selection = meta.get("room_selection")
            if selection and selection.get("status") == "pending":
                return record, selection
        return None, None

    async def _mark_selection_confirmed(self, message_record, key: str) -> None:
        meta = dict(message_record.metadata_json or {})
        selection = dict(meta.get(key) or {})
        selection["status"] = "confirmed"
        meta[key] = selection
        message_record.metadata_json = meta
        await self.db.flush()
