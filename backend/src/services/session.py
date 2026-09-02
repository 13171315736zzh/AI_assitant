from src.models.session import MessagePublic, SessionPublic
from src.repositories.session import MessageRepository, SessionRepository
from src.services.agent import AgentService
from src.services.meeting_workflow import MeetingWorkflowService
from src.services.settings import SettingsService
from src.services.travel_workflow import TravelWorkflowService
from src.services.workpackage_workflow import WorkpackageWorkflowService


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
            return memory_snippets, confirmed_position
        return "", None

    async def _generate_reply(
        self,
        user_id: int,
        session_id: str,
        content: str,
        memory_snippets: str,
        confirmed_position: str | None,
    ) -> tuple[str, str, dict | None]:
        db = self.session_repo.db
        for workflow_svc, kwargs in (
            (MeetingWorkflowService(db), {}),
            (WorkpackageWorkflowService(db), {}),
            (TravelWorkflowService(db), {"staff_level": confirmed_position}),
        ):
            workflow = await workflow_svc.try_execute(
                user_id, session_id, content, **kwargs
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

        memory_snippets, confirmed_position = await self._prepare_agent_context(
            user_id, session_id, content
        )
        reply_content, message_type, metadata = await self._generate_reply(
            user_id,
            session_id,
            content,
            memory_snippets,
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", content, "text")
        assistant_msg = await self.message_repo.create(
            session_id,
            "assistant",
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
        self, user_id: int, session_id: str, content: str
    ):
        """Yields user → ack(s) → done（用户消息立即落库，承接语在正式回复前展示）。"""
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            yield "error", {"code": 404, "message": "会话不存在"}
            return
        if record == "ended":
            yield "error", {"code": 400, "message": "会话已结束，无法发送新消息"}
            return

        memory_snippets, confirmed_position = await self._prepare_agent_context(
            user_id, session_id, content
        )

        user_msg = await self.message_repo.create(session_id, "user", content, "text")
        record.message_count += 1
        await self.session_repo.update(record)
        await self.session_repo.db.commit()
        yield "user", {"user_message": _to_message_public(user_msg).model_dump()}

        acks = await self.agent_service.generate_acks(content)
        for ack in acks:
            yield "ack", {"content": ack}

        await self.session_repo.db.commit()

        reply_content, message_type, metadata = await self._generate_reply(
            user_id,
            session_id,
            content,
            memory_snippets,
            confirmed_position,
        )
        assistant_msg = await self.message_repo.create(
            session_id,
            "assistant",
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
        hotel_name: str | None,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        memory_snippets, confirmed_position = await self._prepare_agent_context(
            user_id, session_id, "确认预订方案"
        )
        _ = memory_snippets

        workflow = await TravelWorkflowService(self.session_repo.db).confirm_booking_selection(
            user_id,
            session_id,
            flight_no=flight_no,
            hotel_name=hotel_name,
            staff_level=confirmed_position,
        )
        if not workflow:
            return None

        summary_parts = ["已确认预订方案"]
        if flight_no:
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
        assistant_msg = await self.message_repo.create(
            session_id,
            "assistant",
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

        _, confirmed_position = await self._prepare_agent_context(
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
        assistant_msg = await self.message_repo.create(
            session_id,
            "assistant",
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
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        _, confirmed_position = await self._prepare_agent_context(
            user_id, session_id, "确认工包填报信息"
        )

        workflow = await WorkpackageWorkflowService(
            self.session_repo.db
        ).confirm_workpackage_plan(user_id, session_id, project=project)
        if not workflow:
            return None

        user_content = "确认开始办理工包填报"
        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self.message_repo.create(
            session_id,
            "assistant",
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

        _, confirmed_position = await self._prepare_agent_context(
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
        assistant_msg = await self.message_repo.create(
            session_id,
            "assistant",
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
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        _, confirmed_position = await self._prepare_agent_context(
            user_id, session_id, "确认出差安排"
        )

        workflow = await TravelWorkflowService(self.session_repo.db).confirm_travel_plan(
            user_id,
            session_id,
            staff_level=confirmed_position,
        )
        if not workflow:
            return None

        user_content = "确认开始办理出差安排"
        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self.message_repo.create(
            session_id,
            "assistant",
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

    async def confirm_meeting_plan(
        self,
        user_id: int,
        session_id: str,
    ) -> tuple[MessagePublic, MessagePublic, str] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        _, confirmed_position = await self._prepare_agent_context(
            user_id, session_id, "确认会议预约"
        )

        workflow = await MeetingWorkflowService(self.session_repo.db).confirm_meeting_plan(
            user_id, session_id
        )
        if not workflow:
            return None

        user_content = "确认开始办理会议预约"
        reply_content, message_type, metadata = await self.agent_service.finalize_outgoing(
            session_id,
            user_content,
            workflow[0],
            workflow[1],
            workflow[2],
            confirmed_position,
        )
        user_msg = await self.message_repo.create(session_id, "user", user_content, "text")
        assistant_msg = await self.message_repo.create(
            session_id,
            "assistant",
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
