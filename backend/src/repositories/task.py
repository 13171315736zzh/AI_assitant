from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.task_models import TaskRecord


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_user(
        self,
        user_id: int,
        page: int,
        page_size: int,
        raw_status: str | None = None,
    ) -> tuple[list[TaskRecord], int]:
        base = select(TaskRecord).where(TaskRecord.user_id == user_id)
        count_q = select(func.count()).select_from(TaskRecord).where(TaskRecord.user_id == user_id)

        if raw_status == "cancelled":
            base = base.where(TaskRecord.status == "cancelled")
            count_q = count_q.where(TaskRecord.status == "cancelled")
        elif raw_status == "active":
            base = base.where(TaskRecord.status.in_(("running", "pending", "completed")))
            count_q = count_q.where(TaskRecord.status.in_(("running", "pending", "completed")))

        total = (await self.db.execute(count_q)).scalar_one()
        offset = (page - 1) * page_size
        result = await self.db.execute(
            base.order_by(TaskRecord.created_at.desc()).offset(offset).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_all_by_user(self, user_id: int) -> list[TaskRecord]:
        result = await self.db.execute(
            select(TaskRecord)
            .where(TaskRecord.user_id == user_id)
            .order_by(TaskRecord.created_at.desc())
        )
        return list(result.scalars().all())

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
