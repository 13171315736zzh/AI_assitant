import secrets
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.chat_models import MessageRecord, SessionRecord


def _new_session_id() -> str:
    return f"sess_{secrets.token_hex(6)}"


def _new_message_id() -> str:
    return f"msg_{secrets.token_hex(6)}"


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_user(
        self,
        user_id: int,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[SessionRecord], int]:
        query = select(SessionRecord).where(SessionRecord.user_id == user_id)
        if status:
            query = query.where(SessionRecord.status == status)
        count_query = select(func.count()).select_from(query.subquery())
        total = int((await self.db.execute(count_query)).scalar_one())
        query = (
            query.order_by(SessionRecord.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_id(self, session_id: str, user_id: int) -> SessionRecord | None:
        result = await self.db.execute(
            select(SessionRecord).where(
                SessionRecord.id == session_id,
                SessionRecord.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_admin(self, session_id: str) -> SessionRecord | None:
        result = await self.db.execute(
            select(SessionRecord).where(SessionRecord.id == session_id)
        )
        return result.scalar_one_or_none()

    async def list_all_admin(
        self,
        keyword: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[SessionRecord, object]], int]:
        from src.db.user_model import User

        query = select(SessionRecord, User).join(User, SessionRecord.user_id == User.id)
        if keyword:
            pattern = f"%{keyword}%"
            query = query.where(
                (SessionRecord.title.like(pattern)) | (User.display_name.like(pattern))
            )
        if status:
            query = query.where(SessionRecord.status == status)

        count_stmt = select(func.count()).select_from(query.subquery())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        result = await self.db.execute(
            query.order_by(SessionRecord.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.all()), total

    async def get_stats(self) -> tuple[int, int, int]:
        from datetime import UTC, datetime

        total = int(
            (await self.db.execute(select(func.count()).select_from(SessionRecord))).scalar_one()
        )
        active = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(SessionRecord)
                    .where(SessionRecord.status == "active")
                )
            ).scalar_one()
        )
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_new = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(SessionRecord)
                    .where(SessionRecord.created_at >= today_start)
                )
            ).scalar_one()
        )
        return total, active, today_new

    async def create(self, user_id: int, title: str) -> SessionRecord:
        now = datetime.now(UTC)
        record = SessionRecord(
            id=_new_session_id(),
            user_id=user_id,
            title=title,
            status="active",
            ended_reason=None,
            message_count=0,
            created_at=now,
            updated_at=now,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def update(self, record: SessionRecord, **fields) -> SessionRecord:
        for key, value in fields.items():
            if value is not None and hasattr(record, key):
                setattr(record, key, value)
        record.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def delete(self, record: SessionRecord) -> None:
        from src.db.form_models import FormRecord
        from src.db.task_models import TaskRecord
        from src.db.ticket_models import TicketRecord

        session_id = record.id
        await self.db.execute(delete(MessageRecord).where(MessageRecord.session_id == session_id))
        await self.db.execute(delete(TaskRecord).where(TaskRecord.session_id == session_id))
        await self.db.execute(delete(FormRecord).where(FormRecord.session_id == session_id))
        await self.db.execute(delete(TicketRecord).where(TicketRecord.session_id == session_id))
        await self.db.delete(record)
        await self.db.flush()


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_session(
        self, session_id: str, page: int, page_size: int
    ) -> tuple[list[MessageRecord], int]:
        base = select(MessageRecord).where(MessageRecord.session_id == session_id)
        count_query = select(func.count()).select_from(base.subquery())
        total = int((await self.db.execute(count_query)).scalar_one())
        query = (
            base.order_by(MessageRecord.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def list_recent_for_context(
        self, session_id: str, limit: int = 30
    ) -> list[MessageRecord]:
        query = (
            select(MessageRecord)
            .where(MessageRecord.session_id == session_id)
            .order_by(MessageRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        records = list(result.scalars().all())
        records.reverse()
        return records

    async def create(
        self,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: dict | None = None,
    ) -> MessageRecord:
        record = MessageRecord(
            id=_new_message_id(),
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            metadata_json=metadata,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record
