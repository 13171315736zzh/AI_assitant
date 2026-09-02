from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.system_config_models import SystemConfigRecord

DEFAULT_SYSTEM_CONFIG = {
    "system_name": "智能办公助手 · 国能集团",
    "welcome_message": "您好，我是国能办公助手，有什么可以帮您？",
    "default_model": "qwen-max",
    "temperature": 0.7,
    "session_retention_days": 90,
    "max_concurrent_sessions": 3,
    "log_level": "INFO",
    "api_timeout_seconds": 60,
}


class SystemConfigRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self) -> SystemConfigRecord:
        result = await self.db.execute(
            select(SystemConfigRecord).where(SystemConfigRecord.id == "default")
        )
        record = result.scalar_one_or_none()
        if record is None:
            record = SystemConfigRecord(id="default", config_json=dict(DEFAULT_SYSTEM_CONFIG))
            self.db.add(record)
            await self.db.flush()
            await self.db.refresh(record)
        return record

    async def save(self, record: SystemConfigRecord) -> SystemConfigRecord:
        await self.db.flush()
        await self.db.refresh(record)
        return record
