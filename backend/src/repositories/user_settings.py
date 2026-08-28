from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.user_settings_models import UserSettingsRecord


class UserSettingsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: int) -> UserSettingsRecord | None:
        result = await self.db.execute(
            select(UserSettingsRecord).where(UserSettingsRecord.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        theme: str = "light",
        memory_enabled: bool = True,
        memory_items_json: list | None = None,
        structured_json: dict | None = None,
    ) -> UserSettingsRecord:
        record = UserSettingsRecord(
            user_id=user_id,
            theme=theme,
            memory_enabled=memory_enabled,
            memory_items_json=memory_items_json or [],
            structured_json=structured_json or {},
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def save(self, record: UserSettingsRecord) -> UserSettingsRecord:
        await self.db.flush()
        await self.db.refresh(record)
        return record
