from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.project_mapping_models import ProjectMappingRecord


class ProjectMappingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self, keyword: str | None = None) -> list[ProjectMappingRecord]:
        query = select(ProjectMappingRecord).order_by(ProjectMappingRecord.project_name)
        if keyword:
            like = f"%{keyword}%"
            query = query.where(
                or_(
                    ProjectMappingRecord.project_name.like(like),
                    ProjectMappingRecord.aliases.like(like),
                    ProjectMappingRecord.city.like(like),
                )
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(ProjectMappingRecord))
        return int(result.scalar_one())

    async def get_by_id(self, mapping_id: str) -> ProjectMappingRecord | None:
        result = await self.db.execute(
            select(ProjectMappingRecord).where(ProjectMappingRecord.id == mapping_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, project_name: str) -> ProjectMappingRecord | None:
        result = await self.db.execute(
            select(ProjectMappingRecord).where(ProjectMappingRecord.project_name == project_name)
        )
        return result.scalar_one_or_none()

    async def create(self, record: ProjectMappingRecord) -> ProjectMappingRecord:
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def update(self, record: ProjectMappingRecord, **fields) -> ProjectMappingRecord:
        for key, value in fields.items():
            if value is not None:
                setattr(record, key, value)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def delete(self, record: ProjectMappingRecord) -> None:
        await self.db.delete(record)

    async def delete_all(self) -> int:
        records = await self.list_all()
        for record in records:
            await self.db.delete(record)
        return len(records)
