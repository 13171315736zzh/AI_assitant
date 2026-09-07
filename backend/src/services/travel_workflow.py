"""差旅办事流程执行：创建任务、表单并返回结构化回复。"""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.session_context import (
    extend_user_messages,
    has_pending_plan,
    load_session_context,
)
from src.agent.travel_workflow import (
    TravelPlan,
    apply_email_plan_draft,
    apply_memory_travel_hints,
    apply_travel_plan_draft,
    build_booking_selection_content,
    build_booking_selection_metadata,
    build_email_plan_confirm_content,
    build_email_plan_confirm_metadata,
    build_email_execution_summary,
    build_email_task_metadata,
    build_booking_tasks_execution_summary,
    build_execution_summary,
    build_hotel_task_metadata,
    build_task_metadata,
    build_transport_task_metadata,
    build_travel_plan,
    build_travel_plan_confirm_content,
    build_travel_plan_confirm_metadata,
    can_present_email_confirm,
    configure_email_only_plan,
    email_only_missing_slots,
    enrich_email_plan_from_memory,
    is_email_only_ready,
    is_email_workflow_intent,
    is_ready_for_hotel_booking,
    is_ready_for_transport_booking,
    is_ready_to_execute,
    is_travel_plan_update,
    is_travel_workflow_intent,
    is_travel_workflow_intent_with_memory,
    missing_hotel_booking_slots,
    missing_transport_booking_slots,
    resolve_transport_booking_type,
    _extract_travel_purpose,
)
from src.agent.workflow_confirm import (
    get_pending_meta,
    is_meta_confirmed,
    mark_meta_confirmed,
    mark_meta_superseded,
)
from src.agent.workflow_plan import (
    activated_plan_node,
    get_workflow_plan_from_session,
    is_parallel_workflow_plan,
    link_task_to_plan,
    match_node_from_text,
    match_plan_node_from_text,
    node_ids_for_travel_task,
    should_service_handle_activation,
    _node_by_id,
)
from src.db.task_models import TaskRecord
from src.integrations.mock_travel_provider import query_travel_bookings
from src.repositories.form import FormRepository
from src.repositories.session import MessageRepository
from src.repositories.task import TaskRepository
from src.repositories.user import UserRepository
from src.repositories.user_settings import UserSettingsRepository
from src.services.form import FormService
from src.services.project_mapping import ProjectMappingService
from src.services.settings import SettingsService


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
        *,
        card_draft: dict | None = None,
    ) -> tuple[str, str, dict] | None:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            return None

        from types import SimpleNamespace

        ctx = await load_session_context(
            self.message_repo, session_id, user_content=user_content
        )
        full_history = ctx.user_messages
        structured = await SettingsService(
            UserSettingsRepository(self.db), self.user_repo
        ).get_user_structured_memory(user_id)

        wf_plan = await get_workflow_plan_from_session(self.message_repo, session_id)
        email_only_mode = self._should_run_email_only(
            user_content, ctx.combined_text, wf_plan, structured
        )
        if email_only_mode:
            return await self._try_email_only(
                user_id,
                session_id,
                user_content,
                staff_level,
                structured=structured,
                full_history=full_history,
                card_draft=card_draft,
            )

        if wf_plan and activated_plan_node(user_content, wf_plan) == "email":
            return await self._try_email_only(
                user_id,
                session_id,
                user_content,
                staff_level,
                structured=structured,
                full_history=full_history,
                card_draft=card_draft,
            )

        if not should_service_handle_activation("travel", user_content, wf_plan):
            return None

        if not is_travel_workflow_intent_with_memory(ctx.combined_text, structured):
            pending_plan_msg, pending_plan = await get_pending_meta(
                self.message_repo, session_id, "travel_plan_confirm"
            )
            if not (has_pending_plan(pending_plan) and is_travel_plan_update(user_content)):
                return None
        else:
            pending_plan_msg, pending_plan = await get_pending_meta(
                self.message_repo, session_id, "travel_plan_confirm"
            )

        has_pending_plan_flag = has_pending_plan(pending_plan)
        parallel_plan = is_parallel_workflow_plan(wf_plan)
        if parallel_plan and not has_pending_plan_flag:
            travel_node = activated_plan_node(user_content, wf_plan)
            travel_nodes = {"travel", "booking", "hotel"}
            if travel_node not in travel_nodes and not is_travel_workflow_intent_with_memory(
                user_content, structured
            ):
                if not is_travel_plan_update(user_content):
                    return None

        plan = build_travel_plan(
            full_history,
            staff_level=staff_level,
            memory_structured=structured,
        )
        plan = apply_memory_travel_hints(plan, structured, ctx.combined_text)
        await self._apply_project_mapping(plan, ctx.merged_text)

        booking_kind = self._resolve_booking_kind(user_content, wf_plan)

        pending_msg, pending_sel = await self._get_pending_booking_selection(
            session_id, booking_kind=booking_kind
        )
        if pending_msg and pending_sel:
            transport_type = pending_sel.get("transport_type")
            if pending_sel.get("booking_kind") == "transport":
                label = "航班" if transport_type == "flight" else "火车/高铁"
            else:
                label = "酒店"
            return (
                f"👇 请先点选{label}，完成后点击「确认预订」。",
                "text",
                {"interactive": True, "booking_selection": pending_sel},
            )

        if booking_kind:
            plan_confirmed = await is_meta_confirmed(
                self.message_repo, session_id, "travel_plan_confirm"
            )
            return await self._try_booking_selection_flow(
                user_id,
                session_id,
                plan,
                user,
                booking_kind,
                user_content=user_content,
                plan_confirmed=plan_confirmed,
                wf_plan=wf_plan,
            )

        if not is_ready_to_execute(plan):
            return None

        if not plan.trip_days and (plan.departure_hint or plan.return_hint):
            plan.trip_days = max(plan.trip_days or 1, 1)

        if pending_plan_msg and has_pending_plan_flag:
            mark_meta_superseded(pending_plan_msg, "travel_plan_confirm")
            await self.db.flush()

        plan_confirmed = await is_meta_confirmed(
            self.message_repo, session_id, "travel_plan_confirm"
        )

        if not plan_confirmed:
            content = build_travel_plan_confirm_content(
                plan, updated=has_pending_plan_flag
            )
            metadata = build_travel_plan_confirm_metadata(plan)
            return content, "text", metadata

        if await self._travel_task_created(session_id):
            if not is_travel_plan_update(user_content):
                return None
            content = build_travel_plan_confirm_content(plan, updated=True)
            metadata = build_travel_plan_confirm_metadata(plan)
            return content, "text", metadata

        return await self._create_task_reply(
            user_id, session_id, plan, user, booking={"flights": [], "hotels": []}
        )

    async def confirm_travel_plan(
        self,
        user_id: int,
        session_id: str,
        staff_level: str | None = None,
        *,
        supplementary_content: str | None = None,
        recipient: str | None = None,
        cc: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        signature: str | None = None,
        origin: str | None = None,
        destination: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        purpose: str | None = None,
        transport_mode: str | None = None,
        transport_other: str | None = None,
        card_draft: dict | None = None,
    ) -> tuple[str, str, dict] | None:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            return None

        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, "travel_plan_confirm"
        )
        if pending_msg is None or pending is None:
            return None

        ctx = await load_session_context(self.message_repo, session_id)
        structured, memory_items, display_name = await self._load_email_memory_context(user_id)
        user_messages = extend_user_messages(ctx.user_messages, supplementary_content)
        plan = build_travel_plan(
            user_messages,
            staff_level=staff_level,
            memory_structured=structured,
        )
        merge_text = ctx.merged_text
        if supplementary_content:
            merge_text = f"{merge_text}\n{supplementary_content.strip()}"
        await self._apply_project_mapping(plan, merge_text)
        self._restore_plan_flags_from_pending(plan, pending)
        card_payload = self._travel_card_payload(card_draft)
        inline_draft = {
            key: value
            for key, value in {
                "origin": origin,
                "destination": destination,
                "start_date": start_date,
                "end_date": end_date,
                "purpose": purpose,
                "transport_mode": transport_mode,
                "transport_other": transport_other,
            }.items()
            if value is not None
        }
        merged_draft = {**card_payload, **inline_draft}
        if pending and pending.get("email_only"):
            plan = configure_email_only_plan(plan)
            plan = apply_email_plan_draft(plan, merged_draft)
            plan = apply_email_plan_draft(
                plan,
                {
                    "recipient": recipient,
                    "cc": cc,
                    "subject": subject,
                    "body": body,
                    "signature": signature,
                },
            )
            plan = enrich_email_plan_from_memory(
                plan, structured, display_name, memory_items
            )
            if not is_email_only_ready(plan):
                return None
        else:
            plan = apply_travel_plan_draft(plan, merged_draft)
            if not is_ready_to_execute(plan):
                return None

        if not plan.trip_days and (plan.needs_transport or plan.needs_hotel):
            plan.trip_days = 1

        mark_meta_confirmed(pending_msg, "travel_plan_confirm")
        await self.db.flush()

        return await self._create_task_reply(
            user_id, session_id, plan, user, booking={"flights": [], "hotels": []}
        )

    async def confirm_booking_selection(
        self,
        user_id: int,
        session_id: str,
        flight_no: str | None = None,
        train_no: str | None = None,
        hotel_name: str | None = None,
        staff_level: str | None = None,
    ) -> tuple[str, str, dict] | None:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            return None

        ctx = await load_session_context(self.message_repo, session_id)
        structured = await SettingsService(
            UserSettingsRepository(self.db), self.user_repo
        ).get_user_structured_memory(user_id)
        plan = build_travel_plan(
            ctx.user_messages,
            staff_level=staff_level,
            memory_structured=structured,
        )
        await self._apply_project_mapping(plan, ctx.merged_text)
        if not is_ready_to_execute(plan):
            return None

        pending_msg, pending_sel = await self._get_pending_booking_selection(session_id)
        if pending_msg is None or pending_sel is None:
            return None

        booking_kind = pending_sel.get("booking_kind")
        flights = pending_sel.get("flights") or []
        trains = pending_sel.get("trains") or []
        hotels = pending_sel.get("hotels") or []
        transport_type = pending_sel.get("transport_type", "flight")

        selected_transport = None
        needs_transport = pending_sel.get("needs_flight", plan.needs_transport)
        if needs_transport and booking_kind == "transport":
            if transport_type == "train":
                if not train_no:
                    return None
                selected_transport = next(
                    (t for t in trains if t.get("train_no") == train_no), None
                )
            else:
                if not flight_no:
                    return None
                selected_transport = next(
                    (f for f in flights if f.get("flight_no") == flight_no), None
                )
            if selected_transport is None:
                return None

        selected_hotel = None
        needs_hotel = pending_sel.get("needs_hotel", plan.needs_hotel)
        if needs_hotel:
            if not hotel_name:
                return None
            selected_hotel = next(
                (h for h in hotels if h.get("name") == hotel_name), None
            )
            if selected_hotel is None:
                return None

        booking = {
            "flights": [selected_transport] if selected_transport else [],
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
        flights = booking.get("flights") or []
        hotels = booking.get("hotels") or []
        if (flights or hotels) and not plan.email_only:
            return await self._create_booking_tasks_reply(
                user_id, session_id, plan, user, booking
            )

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

        travel_form = None
        email_form_id = None
        if plan.email_only:
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
        else:
            travel_form = await self.form_service.preview(
                user_id,
                "travel",
                session_id,
                task_id,
                self._travel_fields(plan),
            )
            for step in steps:
                if step["tool"] == "travel_apply" and travel_form:
                    step["status"] = "completed"
                    step["result"] = {
                        "form_id": travel_form.form_id,
                        "receipt_id": "TA-PENDING",
                    }

        await self.task_repo.update(task, steps_json=steps, current_step=2)

        if plan.email_only:
            await link_task_to_plan(
                self.message_repo,
                session_id,
                task_id,
                category="email",
                node_id="email",
            )
        else:
            await link_task_to_plan(
                self.message_repo,
                session_id,
                task_id,
                category="travel",
                node_id="travel",
            )

        content = (
            build_email_execution_summary(plan, task_id)
            if plan.email_only
            else build_execution_summary(plan, user.display_name, task_id, booking=booking)
        )
        metadata = (
            build_email_task_metadata(plan, task_id, email_form_id, session_id)
            if plan.email_only
            else build_task_metadata(plan, task_id)
        )
        return content, "task", metadata

    async def _create_booking_tasks_reply(
        self,
        user_id: int,
        session_id: str,
        plan: TravelPlan,
        user,
        booking: dict,
    ) -> tuple[str, str, dict]:
        related_metas: list[dict] = []
        flights = booking.get("flights") or []
        hotels = booking.get("hotels") or []

        if flights:
            meta = await self._create_single_booking_task(
                user_id,
                session_id,
                plan,
                user,
                kind="transport",
                selected=flights[0],
            )
            related_metas.append(meta)

        if hotels:
            meta = await self._create_single_booking_task(
                user_id,
                session_id,
                plan,
                user,
                kind="hotel",
                selected=hotels[0],
            )
            related_metas.append(meta)

        if not related_metas:
            return await self._create_task_reply(
                user_id, session_id, plan, user, {"flights": [], "hotels": []}
            )

        content = build_booking_tasks_execution_summary(plan, related_metas)

        if len(related_metas) == 1:
            single = related_metas[0]
            return content, "task", single

        return content, "text", {
            "related_tasks": related_metas,
            "task_id": related_metas[0]["task_id"],
            "task_title": f"{plan.destination or '出行'}预订",
            "progress": "进行中",
            "progress_percent": 50,
            "steps_desc": "交通预订 · 酒店预订",
        }

    async def _create_single_booking_task(
        self,
        user_id: int,
        session_id: str,
        plan: TravelPlan,
        user,
        *,
        kind: str,
        selected: dict,
    ) -> dict:
        task_id = _new_task_id()
        structured = await SettingsService(
            UserSettingsRepository(self.db), self.user_repo
        ).get_user_structured_memory(user_id)

        if kind == "transport":
            tool = "flight_book"
            action = "交通预订"
            form_type = "transport_book"
            fields = self._transport_book_fields(plan, user, structured, selected)
            node_id = "booking"
            metadata_builder = build_transport_task_metadata
        else:
            tool = "hotel_book"
            action = "酒店预订"
            form_type = "hotel_book"
            fields = self._hotel_book_fields(plan, user, structured, selected)
            node_id = "hotel"
            metadata_builder = build_hotel_task_metadata

        steps = [
            {
                "step_id": 1,
                "action": action,
                "tool": tool,
                "status": "running",
                "depends_on": [],
                "params": {"destination": plan.destination or ""},
                "result": {"selected": selected},
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
            goal=plan.raw_goal[:500] or f"{plan.destination or '出行'}{action}",
            status="running",
            current_step=1,
            total_steps=2,
            replan_count=0,
            steps_json=steps,
            created_at=datetime.now(UTC),
        )
        await self.task_repo.create(task)

        form = await self.form_service.preview(
            user_id, form_type, session_id, task_id, fields
        )
        if form:
            steps[0]["status"] = "completed"
            steps[0]["result"] = {
                "selected": selected,
                "form_id": form.form_id,
                "receipt_id": "BK-PENDING",
            }

        await self.task_repo.update(task, steps_json=steps, current_step=2)
        await link_task_to_plan(
            self.message_repo,
            session_id,
            task_id,
            node_id=node_id,
        )

        return metadata_builder(plan, task_id, selected)

    @staticmethod
    def _transport_book_fields(
        plan: TravelPlan,
        user,
        structured: dict,
        transport: dict,
    ) -> dict[str, str]:
        name = str(structured.get("display_name") or user.display_name or "").strip()
        employee_id = str(structured.get("employee_id") or user.employee_id or "").strip()
        phone = str(structured.get("phone") or structured.get("mobile") or "").strip()
        dep_time = str(transport.get("departure_time") or "")
        dep_date = dep_time.split(" ")[0] if dep_time else ""
        dep_clock = dep_time.split(" ")[1] if " " in dep_time else dep_time
        amount = transport.get("price")
        ticket_no = str(
            transport.get("train_no") or transport.get("flight_no") or "—"
        )
        return {
            "passenger_name": name,
            "id_number": employee_id if len(employee_id) >= 15 else "110101199001011234",
            "phone": phone or "13800138000",
            "departure_date": dep_date,
            "departure_time": dep_clock or "—",
            "flight_no": ticket_no,
            "origin": str(transport.get("origin") or plan.origin or "北京"),
            "destination": str(transport.get("destination") or plan.destination or "—"),
            "amount": str(amount) if amount is not None else "—",
        }

    @staticmethod
    def _hotel_book_fields(
        plan: TravelPlan,
        user,
        structured: dict,
        hotel: dict,
    ) -> dict[str, str]:
        name = str(structured.get("display_name") or user.display_name or "").strip()
        employee_id = str(structured.get("employee_id") or user.employee_id or "").strip()
        phone = str(structured.get("phone") or structured.get("mobile") or "").strip()
        amount = hotel.get("price_per_night")
        return {
            "guest_name": name,
            "id_number": employee_id if len(employee_id) >= 15 else "110101199001011234",
            "phone": phone or "13800138000",
            "check_in": str(hotel.get("check_in") or "—"),
            "check_out": str(hotel.get("check_out") or "—"),
            "hotel_name": str(hotel.get("name") or "—"),
            "room_type": str(hotel.get("room_type") or "标准间"),
            "amount": str(amount) if amount is not None else "—",
        }

    @staticmethod
    def _should_run_email_only(
        user_content: str,
        combined_text: str,
        wf_plan: dict | None,
        structured: dict | None,
    ) -> bool:
        if not is_email_workflow_intent(user_content):
            return False

        if wf_plan:
            plan_node = match_plan_node_from_text(user_content, wf_plan)
            if plan_node == "email":
                return True
            if wf_plan.get("active_node_id") == "email":
                return True

        if is_travel_workflow_intent(user_content):
            return False
        if is_travel_workflow_intent_with_memory(combined_text, structured):
            return False

        if wf_plan:
            active_id = wf_plan.get("active_node_id")
            if active_id in ("travel", "booking", "hotel"):
                return False
            plan_node = match_plan_node_from_text(user_content, wf_plan)
            if plan_node in ("travel", "booking", "hotel"):
                return False
            return False
        return True

    async def _try_email_only(
        self,
        user_id: int,
        session_id: str,
        user_content: str,
        staff_level: str | None,
        *,
        structured: dict | None,
        full_history,
        card_draft: dict | None = None,
    ) -> tuple[str, str, dict] | None:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            return None

        structured, memory_items, display_name = await self._load_email_memory_context(user_id)

        pending_plan_msg, pending_plan = await get_pending_meta(
            self.message_repo, session_id, "travel_plan_confirm"
        )
        has_pending_plan_flag = has_pending_plan(pending_plan)
        email_pending = bool(pending_plan and pending_plan.get("email_only"))

        if not email_pending and not is_email_workflow_intent(user_content):
            if not (has_pending_plan_flag and is_travel_plan_update(user_content)):
                return None

        plan = build_travel_plan(
            full_history,
            staff_level=staff_level,
            memory_structured=structured,
        )
        plan = configure_email_only_plan(plan)
        plan = apply_email_plan_draft(plan, self._travel_card_payload(card_draft))
        plan = enrich_email_plan_from_memory(
            plan, structured, display_name, memory_items
        )

        if pending_plan_msg and has_pending_plan_flag:
            mark_meta_superseded(pending_plan_msg, "travel_plan_confirm")
            await self.db.flush()

        if not can_present_email_confirm(plan):
            missing = email_only_missing_slots(plan)
            return (
                "请补充邮件信息：**"
                + "、".join(missing)
                + "**。例如：「发邮件给张经理，主题出差安排确认」。",
                "text",
                None,
            )

        content = build_email_plan_confirm_content(
            plan,
            updated=has_pending_plan_flag,
            structured=structured,
            display_name=display_name,
            memory_items=memory_items,
        )
        metadata = build_email_plan_confirm_metadata(
            plan,
            structured=structured,
            display_name=display_name,
            memory_items=memory_items,
        )
        return content, "text", metadata

    @staticmethod
    def _travel_card_payload(card_draft: dict | None) -> dict:
        if not card_draft or card_draft.get("meta_key") != "travel_plan_confirm":
            return {}
        payload = card_draft.get("payload")
        return dict(payload) if isinstance(payload, dict) else {}

    async def _load_email_memory_context(self, user_id: int) -> tuple[dict, list[dict], str]:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            return {}, [], ""
        settings_svc = SettingsService(
            UserSettingsRepository(self.db), self.user_repo
        )
        memory = await settings_svc.get_memory(user_id)
        structured = memory.structured.model_dump()
        memory_items = [item.model_dump() for item in memory.memory_items]
        display_name = str(structured.get("display_name") or user.display_name or "").strip()
        return structured, memory_items, display_name

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
        if pending.get("email_only"):
            configure_email_only_plan(plan)
            if pending.get("recipient"):
                plan.email_recipient = str(pending["recipient"])
            if pending.get("cc") is not None:
                plan.email_cc = str(pending.get("cc") or "")
            if pending.get("subject"):
                plan.email_subject = str(pending["subject"])
            if pending.get("body"):
                plan.email_body = str(pending["body"])
            if pending.get("signature"):
                plan.email_signature = str(pending["signature"])
        if pending.get("needs_transport") is not None:
            plan.needs_transport = bool(pending["needs_transport"])
        if pending.get("needs_hotel") is not None:
            plan.needs_hotel = bool(pending["needs_hotel"])

    @staticmethod
    def _resolve_booking_kind(user_content: str, wf_plan: dict | None) -> str | None:
        node_id = match_node_from_text(user_content)
        if wf_plan:
            plan_node = match_plan_node_from_text(user_content, wf_plan)
            if plan_node in ("booking", "hotel"):
                node_id = plan_node
        if node_id == "booking":
            return "transport"
        if node_id == "hotel":
            return "hotel"
        return None

    async def _travel_task_created(self, session_id: str) -> bool:
        wf_plan = await get_workflow_plan_from_session(self.message_repo, session_id)
        if wf_plan:
            travel_node = _node_by_id(wf_plan, "travel")
            if travel_node and travel_node.get("task_id"):
                return True
        messages = await self.message_repo.list_recent_for_context(session_id, limit=24)
        for record in reversed(messages):
            if record.message_type != "task":
                continue
            meta = record.metadata_json or {}
            if meta.get("category") == "travel":
                return True
        return False

    async def _try_booking_selection_flow(
        self,
        user_id: int,
        session_id: str,
        plan: TravelPlan,
        user,
        booking_kind: str,
        *,
        user_content: str = "",
        plan_confirmed: bool,
        wf_plan: dict | None,
    ) -> tuple[str, str, dict] | None:
        has_travel_node = bool(wf_plan and _node_by_id(wf_plan, "travel"))
        if has_travel_node and not plan_confirmed:
            if is_ready_to_execute(plan):
                content = build_travel_plan_confirm_content(plan)
                metadata = build_travel_plan_confirm_metadata(plan)
                return content, "text", metadata
            return None

        if booking_kind == "transport":
            plan.needs_transport = True
            missing = missing_transport_booking_slots(plan)
            ready = is_ready_for_transport_booking(plan)
        else:
            plan.needs_hotel = True
            missing = missing_hotel_booking_slots(plan)
            ready = is_ready_for_hotel_booking(plan)

        if missing:
            label = "订车票" if booking_kind == "transport" else "订酒店"
            slots = "、".join(missing)
            return (
                f"办理{label}前，请先补充：{slots}。",
                "text",
                {"interactive": False, "missing_slots": missing},
            )
        if not ready:
            return None

        if not plan.trip_days and plan.departure_hint:
            plan.trip_days = 1

        transport_type = (
            resolve_transport_booking_type(user_content, plan)
            if booking_kind == "transport"
            else None
        )
        booking_snapshot = await query_travel_bookings(
            plan, transport_type=transport_type
        )
        booking = booking_snapshot.to_public_dict()
        content = build_booking_selection_content(
            plan,
            booking_kind=booking_kind,
            transport_type=transport_type,
        )
        metadata = build_booking_selection_metadata(
            plan,
            booking,
            booking_kind=booking_kind,
            transport_type=transport_type,
            user_text=user_content,
        )
        return content, "text", metadata

    async def _get_pending_booking_selection(
        self, session_id: str, *, booking_kind: str | None = None
    ):
        messages = await self.message_repo.list_recent_for_context(session_id, limit=12)
        for record in reversed(messages):
            if record.role != "assistant":
                continue
            meta = record.metadata_json or {}
            selection = meta.get("booking_selection")
            if selection and selection.get("status") == "pending":
                sel_kind = selection.get("booking_kind")
                if booking_kind and sel_kind and sel_kind != booking_kind:
                    continue
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
                ticket_id = chosen.get("train_no") or chosen.get("flight_no", "TBD")
                step["status"] = "completed"
                step["result"] = {
                    "order_id": f"TRV-F-{ticket_id}",
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

        if plan.email_only:
            add(
                "邮件通知项目经理",
                "email_notify",
                "running",
                {"recipient": plan.email_recipient or ""},
            )
        else:
            add("差旅申请创建", "travel_apply", "running", {"destination": plan.destination or ""})
        add("用户确认", "user_confirm", "pending")
        return steps

    def _travel_fields(self, plan: TravelPlan) -> dict[str, str]:
        today = datetime.now(UTC).date()
        dep = today + timedelta(days=1)
        ret = dep + timedelta(days=max((plan.trip_days or 3) - 1, 0))
        if plan.departure_hint and re.match(r"^\d{4}-\d{2}-\d{2}$", str(plan.departure_hint)):
            dep = datetime.fromisoformat(str(plan.departure_hint)).date()
        if plan.return_hint and re.match(r"^\d{4}-\d{2}-\d{2}$", str(plan.return_hint)):
            ret = datetime.fromisoformat(str(plan.return_hint)).date()
        purpose = _extract_travel_purpose(plan)
        return {
            "origin": plan.origin or "",
            "destination": plan.destination or "",
            "departure_date": dep.isoformat(),
            "return_date": ret.isoformat(),
            "project": plan.project_name or "关联项目",
            "transport": plan.transport_pref or "高铁/飞机 · 经济舱",
            "description": purpose or plan.raw_goal[:120],
        }

    def _email_fields(self, plan: TravelPlan, sender_name: str) -> dict[str, str]:
        from src.agent.email_etiquette import infer_salutation

        recipient = plan.email_recipient or "项目经理"
        salutation = infer_salutation(recipient, plan.email_recipient_title)
        body_core = (plan.email_body or "").strip()
        if not body_core:
            dest = plan.destination or "出差目的地"
            days = plan.trip_days or 3
            body_core = (
                f"{salutation}\n\n"
                f"您好！我是{sender_name}。计划于近期前往{dest}出差，行程约{days}天，"
                f"特此邮件告知并请您知悉相关项目安排。\n\n"
                f"如有需协调事项，烦请指示。"
            )
        elif not body_core.startswith(salutation):
            body_core = f"{salutation}\n\n{body_core}"
        signature = (plan.email_signature or "").strip()
        body = f"{body_core.rstrip()}\n\n{signature}" if signature else body_core
        to_value = recipient if "@" in recipient else f"{recipient.lower()}@ceic.com"
        return {
            "to": to_value,
            "cc": (plan.email_cc or "").strip(),
            "subject": (plan.email_subject or f"{plan.destination or '事项'}通知").strip(),
            "body": body,
        }
