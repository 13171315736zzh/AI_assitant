import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.ticket_models import TicketRecord


def _new_ticket_id() -> str:
    return f"WO{datetime.now(UTC).strftime('%Y%m%d')}{secrets.token_hex(2).upper()}"


class TicketRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, ticket_id: str) -> TicketRecord | None:
        result = await self.db.execute(select(TicketRecord).where(TicketRecord.id == ticket_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        session_id: str | None,
        title: str,
        description: str,
    ) -> TicketRecord:
        record = TicketRecord(
            id=_new_ticket_id(),
            user_id=user_id,
            session_id=session_id,
            title=title,
            description=description,
            status="pending",
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record
