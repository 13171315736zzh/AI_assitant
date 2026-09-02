"""差旅办事流程执行：创建任务、表单并返回结构化回复。"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.travel_workflow import (
    TravelPlan,
    build_booking_selection_content,
    build_booking_selection_metadata,
    build_execution_summary,
    build_task_metadata,
    build_travel_plan,
    build_travel_plan_confirm_content,
    build_travel_plan_confirm_metadata,
    is_ready_to_execute,
    is_travel_workflow_intent,
)
from src.agent.workflow_confirm import get_pending_meta, is_meta_confirmed, mark_meta_confirmed
from src.db.task_models import TaskRecord
from src.integrations.mock_travel_provider import query_travel_bookings
from src.repositories.form import FormRepository
from src.repositories.session import MessageRepository
from src.repositories.task import TaskRepository
from src.repositories.user import UserRepository
from src.services.form import FormService
from src.services.project_mapping import ProjectMappingService


def _new_task_id() -> str:
    return f"task_{secrets.token_hex(4)}"


class TravelWorkflowService:
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
        staff_level: str | None = None,
    ) -> tuple[str, str, dict] | None:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            return None

        from types import SimpleNamespace

        history = await self.message_repo.list_recent_for_context(session_id, limit=40)
        full_history = list(history) + [SimpleNamespace(role="user", content=user_content)]

        combined_check = " ".join(
            m.content for m in full_history if m.role == "user"
        )
        if not is_travel_workflow_intent(combined_check):
            return None

        plan = build_travel_plan(full_history, staff_level=staff_level)
        await self._apply_project_mapping(plan, combined_check)

        if not is_ready_to_execute(plan):
            return None

        if not plan.trip_days and (plan.needs_transport or plan.needs_hotel):
            plan.trip_days = 1

        pending_plan_msg, pending_plan = await get_pending_meta(
            self.message_repo, session_id, "travel_plan_confirm"
        )
        if pending_plan_msg and pending_plan:
            return (
                "👇 请核对出差信息并点击「确认开始办理」。",
                "text",
                {"interactive": True, "travel_plan_confirm": pending_plan},
            )

        plan_confirmed = await is_meta_confirmed(
            self.message_repo, session_id, "travel_plan_confirm"
        )

        pending_msg, pending_sel = await self._get_pending_booking_selection(session_id)
        if (
            plan_confirmed
            and pending_msg
            and pending_sel
            and (plan.needs_transport or plan.needs_hotel)
        ):
            return (
                "👇 请在下方勾选框中点选航班与酒店，完成后点击「确认预订」。",
                "text",
                {"interactive": True, "booking_selection": pending_sel},
            )

        if not plan_confirmed:
            content = build_travel_plan_confirm_content(plan)
            metadata = build_travel_plan_confirm_metadata(plan)
            return content, "text", metadata

        if plan.needs_transport or plan.needs_hotel:
            booking_snapshot = await query_travel_bookings(plan)
            booking = booking_snapshot.to_public_dict()
            content = build_booking_selection_content(plan)
            metadata = build_booking_selection_metadata(plan, booking)
            return content, "text", metadata

        return await self._create_task_reply(
            user_id, session_id, plan, user, booking={"flights": [], "hotels": []}
        )

    async def confirm_travel_plan(
        self,
        user_id: int,
        session_id: str,
        staff_level: str | None = None,
    ) -> tuple[str, str, dict] | None:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            return None

        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, "travel_plan_confirm"
        )
        if pending_msg is None or pending is None:
            return None

        history = await self.message_repo.list_recent_for_context(session_id, limit=40)
        combined = " ".join(m.content for m in history if m.role == "user")
        plan = build_travel_plan(history, staff_level=staff_level)
        await self._apply_project_mapping(plan, combined)
        if not is_ready_to_execute(plan):
            return None

        self._restore_plan_flags_from_pending(plan, pending)

        if not plan.trip_days and (plan.needs_transport or plan.needs_hotel):
            plan.trip_days = 1

        mark_meta_confirmed(pending_msg, "travel_plan_confirm")
        await self.db.flush()

        if plan.needs_transport or plan.needs_hotel:
            booking_snapshot = await query_travel_bookings(plan)
            booking = booking_snapshot.to_public_dict()
            content = build_booking_selection_content(plan)
            metadata = build_booking_selection_metadata(plan, booking)
            return content, "text", metadata

        return await self._create_task_reply(
            user_id, session_id, plan, user, booking={"flights": [], "hotels": []}
        )

    async def confirm_booking_selection(
        self,
        user_id: int,
        session_id: str,
        flight_no: str | None = None,
        hotel_name: str | None = None,
        staff_level: str | None = None,
    ) -> tuple[str, str, dict] | None:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            return None

        history = await self.message_repo.list_recent_for_context(session_id, limit=40)
        combined = " ".join(m.content for m in history if m.role == "user")
        plan = build_travel_plan(history, staff_level=staff_level)
        await self._apply_project_mapping(plan, combined)
        if not is_ready_to_execute(plan):
            return None

        pending_msg, pending_sel = await self._get_pending_booking_selection(session_id)
        if pending_msg is None or pending_sel is None:
            return None

        flights = pending_sel.get("flights") or []
        hotels = pending_sel.get("hotels") or []

        selected_flight = None
        if plan.needs_transport:
            if not flight_no:
                return None
            selected_flight = next(
                (f for f in flights if f.get("flight_no") == flight_no), None
            )
            if selected_flight is None:
                return None

        selected_hotel = None
        if plan.needs_hotel:
            if not hotel_name:
                return None
            selected_hotel = next(
                (h for h in hotels if h.get("name") == hotel_name), None
            )
            if selected_hotel is None:
                return None

        booking = {
            "flights": [selected_flight] if selected_flight else [],
            "hotels": [selected_hotel] if selected_hotel else [],
        }

        await self._mark_selection_confirmed(pending_msg)

        return await self._create_task_reply(
            user_id, session_id, plan, user, booking=booking
        )

    async def _create_task_reply(
        self,
        user_id: int,
        session_id: str,
        plan: TravelPlan,
        user,
        booking: dict,
    ) -> tuple[str, str, dict]:
        task_id = _new_task_id()
        steps = self._build_steps(plan, user.display_name)
        self._apply_booking_results(steps, booking)
        completed = sum(1 for s in steps if s["status"] == "completed")
        task = TaskRecord(
            id=task_id,
            session_id=session_id,
            user_id=user_id,
            goal=plan.raw_goal[:500] or f"{plan.destination}出差安排",
            status="running",
            current_step=max(completed, 1),
            total_steps=len(steps),
            replan_count=0,
            steps_json=steps,
            created_at=datetime.now(UTC),
        )
        await self.task_repo.create(task)

        travel_form = await self.form_service.preview(
            user_id,
            "travel",
            session_id,
            task_id,
            self._travel_fields(plan),
        )
        if plan.needs_email and plan.email_recipient:
            email_form = await self.form_service.preview(
                user_id,
                "email",
                session_id,
                task_id,
                self._email_fields(plan, user.display_name),
            )
            email_form_id = email_form.form_id if email_form else None
            for step in steps:
                if step["tool"] == "email_notify" and email_form_id:
                    step["status"] = "completed"
                    step["result"] = {"form_id": email_form_id}

        if travel_form:
            for step in steps:
                if step["tool"] == "travel_apply":
                    step["status"] = "completed"
                    step["result"] = {"form_id": travel_form.form_id, "receipt_id": "TA-PENDING"}

        await self.task_repo.update(task, steps_json=steps, current_step=2)

        content = build_execution_summary(
            plan, user.display_name, task_id, booking=booking
        )
        metadata = build_task_metadata(plan, task_id)
        return content, "task", metadata

    async def _apply_project_mapping(self, plan: TravelPlan, text: str) -> None:
        resolved = await ProjectMappingService(self.db).resolve_from_text(text)
        if resolved is None:
            return
        plan.project_name = resolved.project_name
        plan.location_detail = resolved.full_location
        plan.destination = resolved.policy_city or resolved.city or plan.destination

    @staticmethod
    def _restore_plan_flags_from_pending(plan: TravelPlan, pending: dict | None) -> None:
        if not pending:
            return
        if pending.get("needs_transport") is not None:
            plan.needs_transport = bool(pending["needs_transport"])
        if pending.get("needs_hotel") is not None:
            plan.needs_hotel = bool(pending["needs_hotel"])

    async def _get_pending_booking_selection(self, session_id: str):
        messages = await self.message_repo.list_recent_for_context(session_id, limit=12)
        for record in reversed(messages):
            if record.role != "assistant":
                continue
            meta = record.metadata_json or {}
            selection = meta.get("booking_selection")
            if selection and selection.get("status") == "pending":
                return record, selection
        return None, None

    async def _mark_selection_confirmed(self, message_record) -> None:
        meta = dict(message_record.metadata_json or {})
        selection = dict(meta.get("booking_selection") or {})
        selection["status"] = "confirmed"
        meta["booking_selection"] = selection
        message_record.metadata_json = meta
        await self.db.flush()

    @staticmethod
    def _apply_booking_results(steps: list[dict], booking: dict) -> None:
        flights = booking.get("flights") or []
        hotels = booking.get("hotels") or []
        for step in steps:
            if step["tool"] == "flight_book" and flights:
                chosen = flights[0]
                step["status"] = "completed"
                step["result"] = {
                    "order_id": f"TRV-F-{chosen.get('flight_no', 'TBD')}",
                    "selected": chosen,
                    "status": "quoted",
                }
            if step["tool"] == "hotel_book" and hotels:
                chosen = hotels[0]
                step["status"] = "completed"
                step["result"] = {
                    "order_id": f"TRV-H-{chosen.get('name', 'TBD')[:8]}",
                    "selected": chosen,
                    "status": "quoted",
                }

    @staticmethod
    def _booking_from_steps(steps: list[dict]) -> dict | None:
        flights: list[dict] = []
        hotels: list[dict] = []
        for step in steps:
            result = step.get("result") or {}
            if step.get("tool") == "flight_book" and result.get("selected"):
                flights.append(result["selected"])
            if step.get("tool") == "hotel_book" and result.get("selected"):
                hotels.append(result["selected"])
        if not flights and not hotels:
            return None
        return {"flights": flights, "hotels": hotels}

    async def _get_session_task(self, session_id: str, user_id: int):
        from sqlalchemy import select

        from src.db.task_models import TaskRecord

        result = await self.db.execute(
            select(TaskRecord)
            .where(TaskRecord.session_id == session_id, TaskRecord.user_id == user_id)
            .order_by(TaskRecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _build_steps(self, plan: TravelPlan, sender_name: str) -> list[dict]:
        steps: list[dict] = []
        step_id = 1

        def add(action: str, tool: str, status: str = "pending", params: dict | None = None):
            nonlocal step_id
            steps.append(
                {
                    "step_id": step_id,
                    "action": action,
                    "tool": tool,
                    "status": status,
                    "depends_on": [step_id - 1] if step_id > 1 else [],
                    "params": params or {},
                    "result": None,
                }
            )
            step_id += 1

        add("差旅申请创建", "travel_apply", "running", {"destination": plan.destination or ""})
        if plan.needs_email:
            add(
                "邮件通知项目经理",
                "email_notify",
                "running",
                {"recipient": plan.email_recipient or ""},
            )
        if plan.needs_transport:
            add(
                "交通预订",
                "flight_book",
                "running",
                {
                    "route": f"{plan.origin_airport or plan.origin or '北京'}-{plan.destination or ''}",
                    "preference": plan.transport_pref or "经济舱/二等座",
                    "arrival_before": plan.arrival_deadline or "",
                },
            )
        if plan.needs_hotel:
            add(
                "酒店预订",
                "hotel_book",
                "running",
                {
                    "city": plan.destination or "",
                    "nights": max((plan.trip_days or 1) - 1, 1),
                    "max_price": plan.hotel_max_price or "",
                    "max_distance_km": plan.hotel_max_distance_km or "",
                    "room_type": plan.hotel_room_type or "",
                },
            )
        add("用户确认", "user_confirm", "pending")
        return steps

    def _travel_fields(self, plan: TravelPlan) -> dict[str, str]:
        today = datetime.now(UTC).date()
        dep = today + timedelta(days=1)
        days = plan.trip_days or 3
        ret = dep + timedelta(days=max(days - 1, 0))
        return {
            "destination": plan.destination or "",
            "departure_date": dep.isoformat(),
            "return_date": ret.isoformat(),
            "project": plan.project_name or "关联项目",
            "transport": plan.transport_pref or "高铁/飞机 · 经济舱",
            "description": plan.raw_goal[:120],
        }

    def _email_fields(self, plan: TravelPlan, sender_name: str) -> dict[str, str]:
        from src.agent.email_etiquette import infer_salutation

        recipient = plan.email_recipient or "项目经理"
        salutation = infer_salutation(recipient, plan.email_recipient_title)
        dest = plan.destination or "出差目的地"
        days = plan.trip_days or 3
        body = (
            f"{salutation}\n\n"
            f"您好！我是{sender_name}。计划于近期前往{dest}出差，行程约{days}天，"
            f"特此邮件告知并请您知悉相关项目安排。\n\n"
            f"如有需协调事项，烦请指示。\n\n此致\n敬礼"
        )
        return {
            "to": f"{recipient.lower()}@ceic.com",
            "cc": "",
            "subject": f"{dest}出差安排通知",
            "body": body,
        }
