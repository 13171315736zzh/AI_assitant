"""会议预约流程执行。"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.meeting_workflow import (
    MeetingPlan,
    apply_meeting_plan_draft,
    build_combined_execution_summary,
    build_execution_summary,
    build_gn_execution_summary,
    build_gn_task_metadata,
    build_meeting_plan,
    build_meeting_plan_confirm_content,
    build_meeting_plan_confirm_metadata,
    build_room_execution_summary,
    build_room_selection_content,
    build_room_selection_metadata,
    build_room_task_metadata,
    build_task_metadata,
    can_present_meeting_confirm,
    has_meeting_schedule,
    is_meeting_plan_update,
    is_meeting_workflow_intent,
    is_ready_to_execute,
    missing_slots,
    resolve_meeting_datetime,
)
from src.agent.session_context import extend_user_messages, has_pending_plan, load_session_context
from src.agent.workflow_confirm import (
    get_pending_meta,
    is_meta_confirmed,
    mark_meta_confirmed,
    mark_meta_superseded,
)
from src.agent.workflow_plan import link_task_to_plan
from src.db.task_models import TaskRecord
from src.integrations.mock_meeting_provider import (
    query_available_projection_rooms,
    query_room_availability,
)
from src.repositories.form import FormRepository
from src.repositories.session import MessageRepository
from src.repositories.task import TaskRepository
from src.repositories.user import UserRepository
from src.services.form import FormService


def _new_task_id() -> str:
    return f"task_{secrets.token_hex(4)}"


def _card_payload(card_draft: dict | None, meta_key: str) -> dict:
    if not card_draft:
        return {}
    if card_draft.get("meta_key") and card_draft.get("meta_key") != meta_key:
        return {}
    payload = card_draft.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


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
        *,
        card_draft: dict | None = None,
    ) -> tuple[str, str, dict] | None:
        ctx = await load_session_context(
            self.message_repo, session_id, user_content=user_content
        )

        pending_plan_msg, pending_plan = await get_pending_meta(
            self.message_repo, session_id, "meeting_plan_confirm"
        )
        has_pending_plan_flag = has_pending_plan(pending_plan)

        if not is_meeting_workflow_intent(ctx.combined_text):
            if not (has_pending_plan_flag and is_meeting_plan_update(user_content)):
                return None

        plan = build_meeting_plan(ctx.user_messages)
        card_payload = _card_payload(card_draft, "meeting_plan_confirm")
        plan = apply_meeting_plan_draft(plan, card_payload)
        missing = missing_slots(plan)

        if pending_plan_msg and has_pending_plan_flag:
            mark_meta_superseded(pending_plan_msg, "meeting_plan_confirm")
            await self.db.flush()

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
            if can_present_meeting_confirm(plan):
                content = build_meeting_plan_confirm_content(
                    plan, updated=has_pending_plan_flag
                )
                metadata = build_meeting_plan_confirm_metadata(plan)
                return content, "text", metadata
            if missing and not has_pending_plan_flag:
                return (
                    self._missing_slots_prompt(missing, plan),
                    "text",
                    None,
                )
            return None

        if not is_ready_to_execute(plan):
            return None

        return await self._execute_confirmed_plan(user_id, session_id, plan)

    async def confirm_meeting_plan(
        self,
        user_id: int,
        session_id: str,
        *,
        supplementary_content: str | None = None,
        card_draft: dict | None = None,
    ) -> tuple[str, str, dict] | None:
        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, "meeting_plan_confirm"
        )
        if pending_msg is None or pending is None:
            return None

        ctx = await load_session_context(self.message_repo, session_id)
        user_messages = extend_user_messages(ctx.user_messages, supplementary_content)
        plan = build_meeting_plan(user_messages)
        draft = _card_payload(card_draft, "meeting_plan_confirm")
        if not draft and pending:
            draft = {
                key: pending.get(key)
                for key in (
                    "subject",
                    "selected_room",
                    "room",
                    "room_flexible",
                    "attendees",
                    "date_hint",
                    "start_hint",
                    "end_hint",
                )
                if pending.get(key) is not None
            }
        plan = apply_meeting_plan_draft(plan, draft)
        if not is_ready_to_execute(plan):
            return None

        mark_meta_confirmed(pending_msg, "meeting_plan_confirm")
        await self.db.flush()

        return await self._execute_confirmed_plan(user_id, session_id, plan)

    async def _execute_confirmed_plan(
        self,
        user_id: int,
        session_id: str,
        plan: MeetingPlan,
    ) -> tuple[str, str, dict] | None:
        if plan.needs_gn_meeting and not plan.needs_room_booking:
            return await self._create_gn_meeting_task(user_id, session_id, plan)

        if plan.needs_room_booking:
            if plan.room_flexible:
                availability = await query_available_projection_rooms(
                    date_hint=plan.date_hint,
                    start_hint=plan.start_hint,
                    end_hint=plan.end_hint,
                    equipment_pref=plan.equipment_pref or "投影",
                    raw_text=plan.raw_goal,
                )
                pub = availability.to_public_dict()
                content = build_room_selection_content(plan, pub)
                metadata = build_room_selection_metadata(plan, pub)
                return content, "text", metadata

            availability = await query_room_availability(
                plan.room or "236",
                date_hint=plan.date_hint,
                start_hint=plan.start_hint,
                end_hint=plan.end_hint,
                raw_text=plan.raw_goal,
            )
            pub = availability.to_public_dict()

            if not pub["available"]:
                content = build_room_selection_content(plan, pub)
                metadata = build_room_selection_metadata(plan, pub)
                return content, "text", metadata

            room = pub["requested_room"]
            if plan.needs_gn_meeting:
                return await self._create_combined_tasks(
                    user_id, session_id, plan, room, pub
                )
            return await self._create_room_booking_task(
                user_id, session_id, plan, room, pub
            )

        return None

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

        ctx = await load_session_context(self.message_repo, session_id)
        plan = build_meeting_plan(ctx.user_messages)
        plan.needs_gn_meeting = bool(pending.get("needs_gn_meeting"))
        plan.needs_room_booking = True
        if not is_ready_to_execute(plan):
            return None

        await self._mark_selection_confirmed(pending_msg, "room_selection")

        availability = {
            "requested_room": room,
            "time_label": pending.get("time_label", ""),
            "start_time": pending.get("start_time", ""),
            "end_time": pending.get("end_time", ""),
        }
        if plan.needs_gn_meeting:
            return await self._create_combined_tasks(
                user_id, session_id, plan, room, availability
            )
        return await self._create_room_booking_task(
            user_id, session_id, plan, room, availability
        )

    async def _create_gn_meeting_task(
        self,
        user_id: int,
        session_id: str,
        plan: MeetingPlan,
    ) -> tuple[str, str, dict]:
        task_id = _new_task_id()
        schedule = resolve_meeting_datetime(plan)
        time_label = schedule["time_label"]
        steps = [
            {
                "step_id": 1,
                "action": "国能会议预约",
                "tool": "gn_meeting_book",
                "status": "running",
                "depends_on": [],
                "params": {"subject": plan.subject or ""},
                "result": None,
            },
            {
                "step_id": 2,
                "action": "用户确认",
                "tool": "user_confirm",
                "status": "pending",
                "depends_on": [1],
                "params": {},
                "result": None,
            },
        ]

        task = TaskRecord(
            id=task_id,
            session_id=session_id,
            user_id=user_id,
            goal=plan.raw_goal[:500] or f"{plan.subject}国能会议",
            status="running",
            current_step=1,
            total_steps=2,
            replan_count=0,
            steps_json=steps,
            created_at=datetime.now(UTC),
        )
        await self.task_repo.create(task)

        gn_form = await self.form_service.preview(
            user_id,
            "gn_meeting",
            session_id,
            task_id,
            {
                "subject": plan.subject or "国能会议",
                "start_time": schedule["start_time"],
                "end_time": schedule["end_time"],
                "attendees": plan.attendees or "待定",
            },
        )
        if gn_form:
            for step in steps:
                if step["tool"] == "gn_meeting_book":
                    step["status"] = "completed"
                    step["result"] = {"form_id": gn_form.form_id}

        await self.task_repo.update(task, steps_json=steps, current_step=1)
        await link_task_to_plan(
            self.message_repo, session_id, task_id, node_id="gn_meeting"
        )

        content = build_gn_execution_summary(plan, task_id, time_label)
        metadata = build_gn_task_metadata(plan, task_id)
        return content, "task", metadata

    async def _create_room_booking_task(
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
            goal=plan.raw_goal[:500] or f"{plan.subject}会议室预约",
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
        await link_task_to_plan(
            self.message_repo, session_id, task_id, category="meeting"
        )

        content = build_room_execution_summary(plan, task_id, room, time_label)
        metadata = build_room_task_metadata(plan, task_id)
        return content, "task", metadata

    async def _create_combined_tasks(
        self,
        user_id: int,
        session_id: str,
        plan: MeetingPlan,
        room: str,
        availability: dict,
    ) -> tuple[str, str, dict]:
        _, _, room_meta = await self._create_room_booking_task(
            user_id, session_id, plan, room, availability
        )
        _, _, gn_meta = await self._create_gn_meeting_task(user_id, session_id, plan)

        time_label = availability.get("time_label", "")
        content = build_combined_execution_summary(
            plan,
            room_task_id=room_meta["task_id"],
            gn_task_id=gn_meta["task_id"],
            room=room,
            time_label=time_label,
        )
        metadata = {
            "related_tasks": [room_meta, gn_meta],
            "task_id": room_meta["task_id"],
            "task_title": f"{plan.subject or '会议'}办理",
            "progress": "进行中",
            "progress_percent": 33,
            "steps_desc": "线下会议室 · 国能会议",
        }
        return content, "text", metadata

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

    @staticmethod
    def _missing_slots_prompt(missing: list[str], plan: MeetingPlan | None = None) -> str:
        if plan and has_meeting_schedule(plan):
            if missing == ["会议室"]:
                return (
                    "好的，我来帮您预约会议室。已理解您的会议时间，"
                    "请在下方卡片中核对时段；确认后将进入会议室选择。"
                )
            return (
                "好的，我来帮您预约会议。已推断出部分信息，"
                "请在下方卡片中核对并确认。"
            )
        labels = "、".join(missing)
        return (
            f"好的，我来帮您预约会议。还需要您补充：**{labels}**。\n\n"
            "请说明会议类型（国能会/线下会议室）、时间与参会人员，"
            "例如「明天下午2点开功能会议（线上）」或「今晚7点约236会议室」。"
        )
