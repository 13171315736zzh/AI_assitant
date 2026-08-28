from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.task_models import TaskRecord


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, task_id: str, user_id: int) -> TaskRecord | None:
        result = await self.db.execute(
            select(TaskRecord).where(
                TaskRecord.id == task_id,
                TaskRecord.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, record: TaskRecord) -> TaskRecord:
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def update(self, record: TaskRecord, **fields) -> TaskRecord:
        for key, value in fields.items():
            if value is not None and hasattr(record, key):
                setattr(record, key, value)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def exists(self, task_id: str) -> bool:
        result = await self.db.execute(
            select(TaskRecord.id).where(TaskRecord.id == task_id)
        )
        return result.scalar_one_or_none() is not None
