from src.models.session import MessagePublic, SessionPublic
from src.repositories.session import MessageRepository, SessionRepository
from src.services.agent import AgentService


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
    ):
        self.session_repo = session_repo
        self.message_repo = message_repo
        self.agent_service = agent_service or AgentService(message_repo)

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

    async def list_messages(
        self, user_id: int, session_id: str, page: int, page_size: int
    ) -> tuple[list[MessagePublic], int] | None:
        record = await self.session_repo.get_by_id(session_id, user_id)
        if record is None:
            return None
        messages, total = await self.message_repo.list_by_session(session_id, page, page_size)
        return [_to_message_public(m) for m in messages], total

    async def _prepare_send(
        self, user_id: int, session_id: str
    ) -> tuple | None | str:
        record = await self.session_repo.get_by_id(session_id, user_id)
        if record is None:
            return None
        if record.status == "ended":
            return "ended"
        return record

    async def send_message(
        self, user_id: int, session_id: str, content: str
    ) -> tuple[MessagePublic, MessagePublic] | None | str:
        record = await self._prepare_send(user_id, session_id)
        if record is None:
            return None
        if record == "ended":
            return "ended"

        reply_content, message_type, metadata = await self.agent_service.generate_reply(
            session_id, content
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
        if record.title == "新对话" and len(content) <= 30:
            record.title = content[:30]
        await self.session_repo.update(record)
        return _to_message_public(user_msg), _to_message_public(assistant_msg)

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

        user_msg = await self.message_repo.create(session_id, "user", content, "text")
        record.message_count += 1
        if record.title == "新对话" and len(content) <= 30:
            record.title = content[:30]
        await self.session_repo.update(record)
        yield "user", {"user_message": _to_message_public(user_msg).model_dump()}

        acks = await self.agent_service.generate_acks(content)
        for ack in acks:
            yield "ack", {"content": ack}

        reply_content, message_type, metadata = await self.agent_service.generate_reply(
            session_id, content
        )
        assistant_msg = await self.message_repo.create(
            session_id,
            "assistant",
            reply_content,
            message_type,
            metadata=metadata,
        )
        record.message_count += 1
        await self.session_repo.update(record)
        yield "done", {
            "user_message": _to_message_public(user_msg).model_dump(),
            "assistant_message": _to_message_public(assistant_msg).model_dump(),
        }
