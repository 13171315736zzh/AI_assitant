import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.form_models import FormRecord


def _new_form_id() -> str:
    return f"form_{secrets.token_hex(4)}"


class FormRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, form_id: str, user_id: int) -> FormRecord | None:
        result = await self.db.execute(
            select(FormRecord).where(
                FormRecord.id == form_id,
                FormRecord.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        form_type: str,
        title: str,
        fields: dict,
        session_id: str | None = None,
        task_id: str | None = None,
        form_id: str | None = None,
    ) -> FormRecord:
        record = FormRecord(
            id=form_id or _new_form_id(),
            user_id=user_id,
            session_id=session_id,
            task_id=task_id,
            form_type=form_type,
            status="preview",
            title=title,
            fields_json=fields,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def update(self, record: FormRecord, **fields) -> FormRecord:
        for key, value in fields.items():
            if value is not None and hasattr(record, key):
                setattr(record, key, value)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def exists(self, form_id: str) -> bool:
        result = await self.db.execute(
            select(FormRecord.id).where(FormRecord.id == form_id)
        )
        return result.scalar_one_or_none() is not None
