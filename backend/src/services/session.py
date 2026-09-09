from src.models.session import MessagePublic, SessionPublic
from src.repositories.session import MessageRepository, SessionRepository
from src.services.agent import AgentService
from src.services.leave_workflow import LeaveWorkflowService
from src.services.info_collect_workflow import InfoCollectWorkflowService
from src.services.meeting_workflow import MeetingWorkflowService
from src.services.settings import SettingsService
from src.services.travel_workflow import TravelWorkflowService
from src.services.workpackage_workflow import WorkpackageWorkflowService
from src.services.workflow_cancel import WorkflowCancelService


def _to_session_public(record) -> SessionPublic:
    return SessionPublic(
        id=record.id,
        user_id=record.user_id,
        title=record.title,
        status=record.status,
        ended_reason=record.ended_reason,
        message_count=record.message_count,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
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


def _confirm_user_content(default: str, supplementary: str | None) -> str:
    extra = (supplementary or "").strip()
    return extra or default


class SessionService:
    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        agent_service: AgentService | None = None,
        settings_service: SettingsService | None = None,
    ):
        self.session_repo = session_repo
        self.message_repo = message_repo
        self.agent_service = agent_service or AgentService(message_repo)
        self.settings_service = settings_service

    async def _sync_workflow_task_links(
        self, session_id: str, metadata: dict | None
    ) -> None:
        if not isinstance(metadata, dict):
            return
        if not metadata.get("workflow_plan") and not metadata.get("task_id"):
            return
        from src.agent.workflow_plan import link_tasks_from_assistant_metadata

        await link_tasks_from_assistant_metadata(
            self.message_repo, session_id, metadata
        )

    async def _create_assistant_message(
        self,
        session_id: str,
        content: str,
        message_type: str,
        metadata: dict | None = None,
    ):
        assistant_msg = await self.message_repo.create(
            session_id,
            "assistant",
            content,
            message_type,
            metadata=metadata,
        )
        await self._sync_workflow_task_links(session_id, metadata)
        return assistant_msg

    async def list_sessions(
        self, user_id: int, status: str | None, page: int, page_size: int
    ) -> tuple[list[SessionPublic], int]:
        records, total = await self.session_repo.list_by_user(user_id, status, page, page_size)
        return [_to_session_public(r) for r in records], total

    async def create_session(self, user_id: int, title: str) -> SessionPublic:
        record = await self.session_repo.create(user_id, title)
        return _to_session_public(record)

    async def get_session(self, user_id: int, session_id: str) -> SessionPublic | None:
        record = await self.session_repo.get_by_id(session_id, user_id)
        if record is None:
            return None
        return _to_session_public(record)

    async def update_session(
        self,
        user_id: int,
        session_id: str,
        status: str | None,
        ended_reason: str | None,
    ) -> SessionPublic | None:
        record = await self.session_repo.get_by_id(session_id, user_id)
        if record is None:
            return None
        updated = await self.session_repo.update(record, status=status, ended_reason=ended_reason)
        return _to_session_public(updated)

    async def delete_session(self, user_id: int, session_id: str) -> bool:
        record = await self.session_repo.get_by_id(session_id, user_id)
        if record is None:
            return False
        await self.session_repo.delete(record)
        return True

    async def list_messages(
        self, user_id: int, session_id: str, page: int, page_size: int
    ) -> tuple[list[MessagePublic], int] | None:
        record = await self.session_repo.get_by_id(session_id, user_id)
        if record is None:
            return None
        messages, total = await self.message_repo.list_by_session(session_id, page, page_size)
        return [_to_message_public(m) for m in messages], total

    async def _refresh_session_title(self, record) -> str:
        messages, _ = await self.message_repo.list_by_session(record.id, 1, 50)
        user_texts = [m.content for m in messages if m.role == "user" and m.content.strip()]
        if not user_texts:
            return record.title
        title = await self.agent_service.generate_session_title(user_texts)
        if title and title != record.title:
            record.title = title
        return record.title

    async def _prepare_send(
        self, user_id: int, session_id: str
    ) -> tuple | None | str:
        record = await self.session_repo.get_by_id(session_id, user_id)
        if record is None:
            return None
        if record.status == "ended":
            return "ended"
        return record

    async def _assistant_context(self, session_id: str) -> str | None:
        records = await self.message_repo.list_recent_for_context(session_id, limit=6)
        for record in reversed(records):
            if record.role == "assistant" and record.content.strip():
                return record.content
        return None

    async def _prepare_agent_context(
        self, user_id: int, session_id: str, user_content: str
    ) -> tuple[str, str | None]:
        assistant_context = await self._assistant_context(session_id)
        if self.settings_service:
            await self.settings_service.try_extract_position_from_message(
                user_id, user_content, assistant_context
            )
            memory_snippets = await self.settings_service.build_agent_memory_snippets(user_id)
            confirmed_position = await self.settings_service.get_confirmed_position(user_id)
            travel_staff_level = await self.settings_service.get_travel_staff_level(user_id)
            return memory_snippets, confirmed_position, travel_staff_level
        return "", None, "其他人员"

    async def _generate_reply(
        self,
        user_id: int,
        session_id: str,
        content: str,
        memory_snippets: str,
        confirmed_position: str | None,
        travel_staff_level: str = "其他人员",
        *,
        card_draft: dict | None = None,
    ) -> tuple[str, str, dict | None]:
        from src.agent.workflow_cancel import (
            is_meeting_cancel_selection_intent,
            is_workflow_cancel_intent,
            resolve_workflow_cancel_node,
        )
        from src.agent.workflow_plan import (
            get_workflow_plan_from_session,
            prepare_workflow_route,
            sync_workflow_plan_with_message,
            try_session_summary_reply,
        )

        summary_reply = await try_session_summary_reply(
            self.message_repo, session_id, content
        )
        if summary_reply:
            return await self.agent_service.finalize_outgoing(
                session_id,
                content,
                summary_reply[0],
                summary_reply[1],
                summary_reply[2],
                confirmed_position,
            )

        db = self.session_repo.db
        wf_plan, _ = await sync_workflow_plan_with_message(
            self.message_repo, session_id, content
        )
        if wf_plan is None:
            wf_plan = await get_workflow_plan_from_session(self.message_repo, session_id)
        if is_meeting_cancel_selection_intent(content, wf_plan):
            selection_card = await WorkflowCancelService(db).present_meeting_cancel_selection(
                user_id, session_id, wf_plan=wf_plan
            )
            if selection_card:
                return await self.agent_service.finalize_outgoing(
                    session_id,
                    content,
                    selection_card[0],
                    selection_card[1],
                    selection_card[2],
                    confirmed_position,
                )
        if is_workflow_cancel_intent(content, wf_plan):
            node_id = resolve_workflow_cancel_node(content, wf_plan)
            if node_id:
                cancel_card = await WorkflowCancelService(db).present_cancel_confirm(
                    user_id,
                    session_id,
                    node_id=node_id,
                    wf_plan=wf_plan,
                )
                if cancel_card:
                    return await self.agent_service.finalize_outgoing(
                        session_id,
                        content,
                        cancel_card[0],
                        cancel_card[1],
                        cancel_card[2],
                        confirmed_position,
                    )
        preferred_service = await prepare_workflow_route(
            self.message_repo, session_id, content
        )
        workflow_entries: list[tuple[str, object, dict]] = [
            ("meeting", MeetingWorkflowService(db), {}),
            ("workpackage", WorkpackageWorkflowService(db), {}),
            ("leave", LeaveWorkflowService(db), {}),
            ("info_collect", InfoCollectWorkflowService(db), {}),
            ("travel", TravelWorkflowService(db), {"staff_level": travel_staff_level}),
        ]
        if preferred_service:
            workflow_entries.sort(
                key=lambda item: 0 if item[0] == preferred_service else 1
            )
        for _, workflow_svc, kwargs in workflow_entries:
            workflow = await workflow_svc.try_execute(
                user_id,
                session_id,
                content,
                card_draft=card_draft,
                **kwargs,
            )
            if workflow:
                return await self.agent_service.finalize_outgoing(
                    session_id,
                    content,
                    workflow[0],
                    workflow[1],
                    workflow[2],
                    confirmed_position,
                )
        return await self.agent_service.generate_reply(
            session_id,
            content,
            memory_snippets=memory_snippets,
            confirmed_position=confirmed_position,
        )

    async def send_message(
        self, user_id: int, session_id: str, content: str
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        memory_snippets, confirmed_position, travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, content
        )
        reply_content, message_type, metadata = await self._generate_reply(
            user_id,
            session_id,
            content,
            memory_snippets,
            confirmed_position,
            travel_staff_level,
        )
        user_msg = await self.message_repo.create(session_id, "user", content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def stream_reply(
        self, user_id: int, session_id: str, content: str, *, card_draft: dict | None = None
    ):
        """Yields user → ack(s) → done（用户消息立即落库，承接语在正式回复前展示）。"""
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            yield "error", {"code": 404, "message": "会话不存在"}
            return
        if record == "ended":
            yield "error", {"code": 400, "message": "会话已结束，无法发送新消息"}
            return

        memory_snippets, confirmed_position, travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, content
        )

        user_msg = await self.message_repo.create(session_id, "user", content, "text")
        record.message_count += 1
        await self.session_repo.update(record)
        await self.session_repo.db.commit()
        yield "user", {"user_message": _to_message_public(user_msg).model_dump()}

        acks = await self.agent_service.generate_acks(session_id, content)
        for ack in acks:
            yield "ack", {"content": ack}

        await self.session_repo.db.commit()

        reply_content, message_type, metadata = await self._generate_reply(
            user_id,
            session_id,
            content,
            memory_snippets,
            confirmed_position,
            travel_staff_level,
            card_draft=card_draft,
        )
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 1
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        await self.session_repo.db.commit()
        yield "done", {
            "user_message": _to_message_public(user_msg).model_dump(),
            "assistant_message": _to_message_public(assistant_msg).model_dump(),
            "session_title": session_title,
        }

    async def confirm_booking_selection(
        self,
        user_id: int,
        session_id: str,
        flight_no: str | None,
        train_no: str | None,
        hotel_name: str | None,
        drive: bool = False,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        _, confirmed_position, travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, "确认预订方案"
        )

        workflow = await TravelWorkflowService(self.session_repo.db).confirm_booking_selection(
            user_id,
            session_id,
            flight_no=flight_no,
            train_no=train_no,
            hotel_name=hotel_name,
            drive=drive,
            staff_level=travel_staff_level,
        )
        if not workflow:
            return None

        summary_parts = ["已确认预订方案"]
        if drive:
            summary_parts.append("自驾")
        elif train_no:
            summary_parts.append(f"车次 {train_no}")
        elif flight_no:
            summary_parts.append(f"航班 {flight_no}")
        if hotel_name:
            summary_parts.append(f"酒店 {hotel_name}")
        user_content = "，".join(summary_parts)

        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def confirm_room_selection(
        self,
        user_id: int,
        session_id: str,
        room: str,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        _, confirmed_position, travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, "确认会议室"
        )

        workflow = await MeetingWorkflowService(self.session_repo.db).confirm_room_selection(
            user_id, session_id, room
        )
        if not workflow:
            return None

        user_content = f"已确认预约 {room} 会议室"
        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def confirm_workpackage_plan(
        self,
        user_id: int,
        session_id: str,
        *,
        project: str | None = None,
        all_days_eight_hours: bool | None = None,
        hours_per_day: float | None = None,
        supplementary_content: str | None = None,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        user_content = _confirm_user_content("确认开始办理工包填报", supplementary_content)
        _, confirmed_position, travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, user_content
        )

        workflow = await WorkpackageWorkflowService(
            self.session_repo.db
        ).confirm_workpackage_plan(
            user_id,
            session_id,
            project=project,
            all_days_eight_hours=all_days_eight_hours,
            hours_per_day=hours_per_day,
            supplementary_content=supplementary_content,
        )
        if not workflow:
            return None

        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def confirm_workpackage(
        self,
        user_id: int,
        session_id: str,
        *,
        entries: list[dict] | None = None,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        _, confirmed_position, travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, "确认工包填报"
        )

        workflow = await WorkpackageWorkflowService(self.session_repo.db).confirm_workpackage(
            user_id, session_id, entries=entries
        )
        if not workflow:
            return None

        user_content = "确认按上述计划填报工包"
        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def confirm_travel_plan(
        self,
        user_id: int,
        session_id: str,
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
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        from src.agent.workflow_confirm import get_pending_meta

        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        _, pending = await get_pending_meta(
            self.message_repo, session_id, "travel_plan_confirm"
        )
        default_label = "确认开始办理出差安排"
        if pending and pending.get("email_only"):
            default_label = "确认并开始写邮件"

        user_content = _confirm_user_content(default_label, supplementary_content)
        _, confirmed_position, travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, user_content
        )

        workflow = await TravelWorkflowService(self.session_repo.db).confirm_travel_plan(
            user_id,
            session_id,
            staff_level=travel_staff_level,
            supplementary_content=supplementary_content,
            recipient=recipient,
            cc=cc,
            subject=subject,
            body=body,
            signature=signature,
            origin=origin,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            purpose=purpose,
            transport_mode=transport_mode,
            transport_other=transport_other,
            card_draft=card_draft,
        )
        if not workflow:
            return None

        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def request_workflow_cancel_confirm(
        self,
        user_id: int,
        session_id: str,
        *,
        task_id: str | None = None,
        node_id: str | None = None,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        from src.agent.workflow_cancel import node_label

        record = await self.session_repo.get_by_id(session_id, user_id)
        if record is None:
            return None
        if record.status == "ended":
            return "ended"

        label = node_label(node_id) if node_id else "办理项"
        user_content = f"取消{label}"
        _, confirmed_position, _travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, user_content
        )

        workflow = await WorkflowCancelService(
            self.session_repo.db
        ).present_cancel_confirm(
            user_id, session_id, task_id=task_id, node_id=node_id
        )
        if not workflow:
            return None

        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow_metadata or None,
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def request_room_cancel_confirm(
        self,
        user_id: int,
        session_id: str,
        task_id: str | None = None,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        return await self.request_workflow_cancel_confirm(
            user_id, session_id, task_id=task_id, node_id="room"
        )

    async def confirm_workflow_cancel(
        self,
        user_id: int,
        session_id: str,
        task_id: str,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        user_content = "确认取消办理"
        _, confirmed_position, _travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, user_content
        )

        workflow = await WorkflowCancelService(self.session_repo.db).confirm_cancel(
            user_id, session_id, task_id
        )
        if not workflow:
            return None

        from src.agent.workflow_plan import get_workflow_plan_from_session

        workflow_metadata = dict(workflow[2] or {})
        fresh_plan = await get_workflow_plan_from_session(self.message_repo, session_id)
        if fresh_plan:
            workflow_metadata["workflow_plan"] = fresh_plan

        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow_metadata or None,
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def confirm_meeting_cancel_selection(
        self,
        user_id: int,
        session_id: str,
        node_ids: list[str],
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        user_content = "确认取消会议选择"
        _, confirmed_position, _travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, user_content
        )

        workflow = await WorkflowCancelService(
            self.session_repo.db
        ).confirm_meeting_cancel_selection(user_id, session_id, node_ids)
        if not workflow:
            return None

        from src.agent.workflow_plan import get_workflow_plan_from_session

        workflow_metadata = dict(workflow[2] or {})
        fresh_plan = await get_workflow_plan_from_session(self.message_repo, session_id)
        if fresh_plan:
            workflow_metadata["workflow_plan"] = fresh_plan

        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow_metadata or None,
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def confirm_room_cancel(
        self,
        user_id: int,
        session_id: str,
        task_id: str,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        return await self.confirm_workflow_cancel(user_id, session_id, task_id)

    async def confirm_meeting_plan(
        self,
        user_id: int,
        session_id: str,
        *,
        supplementary_content: str | None = None,
        card_draft: dict | None = None,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        user_content = _confirm_user_content("确认开始办理会议预约", supplementary_content)
        _, confirmed_position, travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, user_content
        )

        workflow = await MeetingWorkflowService(self.session_repo.db).confirm_meeting_plan(
            user_id,
            session_id,
            supplementary_content=supplementary_content,
            card_draft=card_draft,
        )
        if not workflow:
            return None

        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def confirm_leave_plan(
        self,
        user_id: int,
        session_id: str,
        *,
        reason: str | None = None,
        attachment_name: str | None = None,
        leave_type: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
        supplementary_content: str | None = None,
        card_draft: dict | None = None,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        user_content = _confirm_user_content("确认提交请假申请", supplementary_content)
        _, confirmed_position, travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, user_content
        )

        workflow = await LeaveWorkflowService(self.session_repo.db).confirm_leave_plan(
            user_id,
            session_id,
            reason=reason,
            attachment_name=attachment_name,
            leave_type=leave_type,
            date_start=date_start,
            date_end=date_end,
            start_period=start_period,
            end_period=end_period,
            supplementary_content=supplementary_content,
            card_draft=card_draft,
        )
        if not workflow:
            return None

        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )

    async def confirm_info_collect_plan(
        self,
        user_id: int,
        session_id: str,
        *,
        structured: dict | None = None,
        supplementary_content: str | None = None,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        user_content = _confirm_user_content("确认保存核心个人信息到长期记忆", supplementary_content)
        _, confirmed_position, travel_staff_level = await self._prepare_agent_context(
            user_id, session_id, user_content
        )

        try:
            workflow = await InfoCollectWorkflowService(self.session_repo.db).confirm_info_collect_plan(
                user_id,
                session_id,
                structured=structured,
                supplementary_content=supplementary_content,
            )
        except ValueError as exc:
            return ("validation_error", str(exc))
        if not workflow:
            return None

        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self._create_assistant_message(
            session_id,
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 2
        session_title = await self._refresh_session_title(record)
        await self.session_repo.update(record)
        return (
            _to_message_public(user_msg),
            _to_message_public(assistant_msg),
            session_title,
        )
