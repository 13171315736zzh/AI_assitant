from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.knowledge_models import DocumentChunkRecord, DocumentRecord, QARecord


def _filename_keywords(filename: str) -> list[str]:
    name = filename.replace(".pdf", "").replace(".docx", "").strip()
    keywords: list[str] = []
    for token in ("差旅", "报销", "管理办法", "实施细则", "办公"):
        if token in name:
            keywords.append(token)
    if not keywords and len(name) >= 4:
        keywords.append(name[:8])
    return keywords


class KnowledgeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_documents(self, page: int, page_size: int) -> tuple[list[DocumentRecord], int]:
        total = int(
            (await self.db.execute(select(func.count()).select_from(DocumentRecord))).scalar_one()
        )
        result = await self.db.execute(
            select(DocumentRecord)
            .where(DocumentRecord.status == "ready")
            .order_by(DocumentRecord.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_admin_documents(self, page: int, page_size: int) -> tuple[list[DocumentRecord], int]:
        total = int(
            (await self.db.execute(select(func.count()).select_from(DocumentRecord))).scalar_one()
        )
        result = await self.db.execute(
            select(DocumentRecord)
            .order_by(DocumentRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_document(self, document_id: str) -> DocumentRecord | None:
        result = await self.db.execute(
            select(DocumentRecord).where(DocumentRecord.id == document_id)
        )
        return result.scalar_one_or_none()

    async def find_document_for_source(
        self, document_id: str | None, filename: str | None
    ) -> DocumentRecord | None:
        from pathlib import Path

        if document_id:
            doc = await self.get_document(document_id)
            if doc and doc.status == "ready" and Path(doc.file_path).is_file():
                return doc
        if filename:
            exact = await self.db.execute(
                select(DocumentRecord).where(
                    DocumentRecord.filename == filename,
                    DocumentRecord.status == "ready",
                )
            )
            doc = exact.scalar_one_or_none()
            if doc and Path(doc.file_path).is_file():
                return doc
            for keyword in _filename_keywords(filename):
                fuzzy = await self.db.execute(
                    select(DocumentRecord)
                    .where(
                        DocumentRecord.status == "ready",
                        DocumentRecord.file_type == "pdf",
                        DocumentRecord.filename.contains(keyword),
                    )
                    .order_by(DocumentRecord.updated_at.desc())
                    .limit(1)
                )
                doc = fuzzy.scalar_one_or_none()
                if doc and Path(doc.file_path).is_file():
                    return doc
        fallback = await self.db.execute(
            select(DocumentRecord)
            .where(DocumentRecord.status == "ready", DocumentRecord.file_type == "pdf")
            .order_by(DocumentRecord.updated_at.desc())
            .limit(1)
        )
        doc = fallback.scalar_one_or_none()
        if doc and Path(doc.file_path).is_file():
            return doc
        return None

    async def document_exists(self, document_id: str) -> bool:
        result = await self.db.execute(
            select(DocumentRecord.id).where(DocumentRecord.id == document_id)
        )
        return result.scalar_one_or_none() is not None

    async def create_document(self, record: DocumentRecord) -> DocumentRecord:
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def save_document(self, record: DocumentRecord) -> DocumentRecord:
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def delete_document(self, document_id: str) -> bool:
        record = await self.get_document(document_id)
        if record is None:
            return False
        await self.db.execute(delete(QARecord).where(QARecord.document_id == document_id))
        await self.db.execute(
            delete(DocumentChunkRecord).where(DocumentChunkRecord.document_id == document_id)
        )
        await self.db.delete(record)
        await self.db.flush()
        return True

    async def list_qa(
        self, keyword: str | None, page: int, page_size: int
    ) -> tuple[list[tuple[QARecord, DocumentRecord | None]], int]:
        filters = []
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(QARecord.question.like(pattern), QARecord.answer.like(pattern)))

        count_stmt = select(func.count()).select_from(QARecord)
        for clause in filters:
            count_stmt = count_stmt.where(clause)
        total = int((await self.db.execute(count_stmt)).scalar_one())

        query = select(QARecord, DocumentRecord).join(
            DocumentRecord, QARecord.document_id == DocumentRecord.id, isouter=True
        )
        for clause in filters:
            query = query.where(clause)
        result = await self.db.execute(
            query.order_by(QARecord.id.asc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.all()), total

    async def list_all_qa_with_docs(self) -> list[tuple[QARecord, DocumentRecord | None]]:
        result = await self.db.execute(
            select(QARecord, DocumentRecord).join(
                DocumentRecord, QARecord.document_id == DocumentRecord.id, isouter=True
            )
        )
        return list(result.all())

    async def create_qa(self, record: QARecord) -> QARecord:
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def replace_qa(self, document_id: str, items: list[QARecord]) -> None:
        await self.db.execute(delete(QARecord).where(QARecord.document_id == document_id))
        for item in items:
            self.db.add(item)
        await self.db.flush()

    async def replace_chunks(self, document_id: str, chunks: list[DocumentChunkRecord]) -> None:
        await self.db.execute(
            delete(DocumentChunkRecord).where(DocumentChunkRecord.document_id == document_id)
        )
        for chunk in chunks:
            self.db.add(chunk)
        await self.db.flush()

    async def list_chunks(self, document_id: str | None = None) -> list[DocumentChunkRecord]:
        query = select(DocumentChunkRecord)
        if document_id:
            query = query.where(DocumentChunkRecord.document_id == document_id)
        result = await self.db.execute(query.order_by(DocumentChunkRecord.chunk_index.asc()))
        return list(result.scalars().all())

    async def search_documents(self, keyword: str, limit: int = 20) -> list[DocumentRecord]:
        pattern = f"%{keyword}%"
        result = await self.db.execute(
            select(DocumentRecord)
            .where(DocumentRecord.status == "ready")
            .where(DocumentRecord.filename.like(pattern))
            .limit(limit)
        )
        return list(result.scalars().all())
