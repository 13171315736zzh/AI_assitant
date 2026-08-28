import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pycore.core import get_logger
from pycore.integrations.llm.base import Message

from src.db.knowledge_models import DocumentChunkRecord, DocumentRecord, QARecord
from src.integrations.document_parser import (
    extract_document_text_async,
    extract_pdf_text,
    guess_clause,
    new_document_id,
    split_text,
)
from src.integrations.llm_factory import create_llm_provider
from src.integrations.text_similarity import text_similarity
from src.models.knowledge import (
    AdminDocumentPublic,
    AdminQAItemPublic,
    DeleteDocumentData,
    DocumentProgressData,
    DocumentPublic,
    DocumentUploadData,
    KnowledgeSearchData,
    QAItemPublic,
    SearchTestData,
    SearchTestResult,
)
from src.repositories.knowledge import KnowledgeRepository

logger = get_logger()

DOCUMENTS_DIR = Path(__file__).resolve().parents[2] / "data" / "documents"
QA_DIRECT_THRESHOLD = 0.8
ALLOWED_TYPES = {"pdf", "docx"}


def _qa_public(qa: QARecord, doc: DocumentRecord | None) -> QAItemPublic:
    return QAItemPublic(
        id=qa.id,
        question=qa.question,
        answer=qa.answer,
        source_clause=qa.source_clause,
        document_name=doc.filename if doc else "",
    )


class KnowledgeService:
    def __init__(self, repo: KnowledgeRepository):
        self.repo = repo

    async def list_public_documents(self, page: int, page_size: int) -> tuple[list[DocumentPublic], int]:
        records, total = await self.repo.list_documents(page, page_size)
        items = [
            DocumentPublic(
                id=record.id,
                filename=record.filename,
                file_type=record.file_type,
                updated_at=record.updated_at.isoformat(),
            )
            for record in records
        ]
        return items, total

    async def list_public_qa(
        self, keyword: str | None, page: int, page_size: int
    ) -> tuple[list[QAItemPublic], int]:
        rows, total = await self.repo.list_qa(keyword, page, page_size)
        items = [_qa_public(qa, doc) for qa, doc in rows]
        return items, total

    async def search(self, query: str) -> KnowledgeSearchData:
        rows = await self.repo.list_all_qa_with_docs()
        qa_results: list[tuple[float, QAItemPublic]] = []
        for qa, doc in rows:
            score = max(text_similarity(query, qa.question), text_similarity(query, qa.answer))
            if score >= 0.35:
                qa_results.append((score, _qa_public(qa, doc)))
        qa_results.sort(key=lambda item: item[0], reverse=True)

        doc_records = await self.repo.search_documents(query)
        document_results = [
            DocumentPublic(
                id=record.id,
                filename=record.filename,
                file_type=record.file_type,
                updated_at=record.updated_at.isoformat(),
            )
            for record in doc_records
        ]
        return KnowledgeSearchData(
            qa_results=[item[1] for item in qa_results[:20]],
            document_results=document_results,
        )

    async def list_admin_documents(self, page: int, page_size: int) -> tuple[list[AdminDocumentPublic], int]:
        records, total = await self.repo.list_admin_documents(page, page_size)
        items = [
            AdminDocumentPublic(
                id=record.id,
                filename=record.filename,
                file_type=record.file_type,
                status=record.status,
                uploaded_by=record.uploaded_by,
                created_at=record.created_at.isoformat(),
                progress_percent=record.progress_percent if record.status != "ready" else None,
            )
            for record in records
        ]
        return items, total

    async def list_admin_qa(
        self, keyword: str | None, page: int, page_size: int
    ) -> tuple[list[AdminQAItemPublic], int]:
        rows, total = await self.repo.list_qa(keyword, page, page_size)
        items = [
            AdminQAItemPublic(
                id=qa.id,
                document_id=qa.document_id,
                question=qa.question,
                answer=qa.answer,
                source_clause=qa.source_clause,
            )
            for qa, _ in rows
        ]
        return items, total

    async def get_document_file(self, document_id: str) -> tuple[Path, str, str] | None:
        record = await self.repo.get_document(document_id)
        if record is None or record.status != "ready":
            return None
        path = Path(record.file_path)
        if not path.is_file():
            return None
        media = "application/pdf" if record.file_type == "pdf" else (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        return path, record.filename, media

    async def get_progress(self, document_id: str) -> DocumentProgressData | None:
        record = await self.repo.get_document(document_id)
        if record is None:
            return None
        return DocumentProgressData(
            id=record.id,
            status=record.status,
            progress={"stage": record.stage, "percent": record.progress_percent},
        )

    async def upload_document(
        self, filename: str, content: bytes, uploaded_by: str
    ) -> DocumentUploadData:
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in ALLOWED_TYPES:
            raise ValueError("仅支持 PDF、Word 文件")

        DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        doc_id = new_document_id()
        stored_name = f"{doc_id}.{ext}"
        file_path = DOCUMENTS_DIR / stored_name
        file_path.write_bytes(content)

        now = datetime.now(UTC)
        record = DocumentRecord(
            id=doc_id,
            filename=filename,
            file_type=ext,
            file_path=str(file_path),
            status="uploading",
            stage="uploading",
            progress_percent=0,
            uploaded_by=uploaded_by,
            created_at=now,
            updated_at=now,
        )
        await self.repo.create_document(record)
        asyncio.create_task(_process_document_async(doc_id))
        return DocumentUploadData(
            id=doc_id,
            filename=filename,
            status="uploading",
            progress={"stage": "uploading", "percent": 0},
        )

    async def reindex_document(self, document_id: str) -> DocumentProgressData | None:
        record = await self.repo.get_document(document_id)
        if record is None:
            return None
        record.status = "parsing"
        record.stage = "parsing"
        record.progress_percent = 10
        await self.repo.save_document(record)
        asyncio.create_task(_process_document_async(document_id))
        return DocumentProgressData(
            id=record.id,
            status=record.status,
            progress={"stage": record.stage, "percent": record.progress_percent},
        )

    async def delete_document(self, document_id: str) -> DeleteDocumentData | None:
        record = await self.repo.get_document(document_id)
        if record is None:
            return None
        path = Path(record.file_path)
        deleted = await self.repo.delete_document(document_id)
        if deleted and path.is_file():
            path.unlink(missing_ok=True)
        return DeleteDocumentData(deleted=deleted)


async def _process_document_async(document_id: str) -> None:
    from src.db.session import get_session

    async with get_session() as db:
        repo = KnowledgeRepository(db)
        record = await repo.get_document(document_id)
        if record is None:
            return

        try:
            record.status = "parsing"
            record.stage = "parsing"
            record.progress_percent = 20
            await repo.save_document(record)

            file_path = Path(record.file_path)

            async def _mark_ocr_start() -> None:
                record.status = "parsing"
                record.stage = "ocr"
                record.progress_percent = 30
                await repo.save_document(record)

            text = await extract_document_text_async(
                file_path, record.file_type, on_ocr_start=_mark_ocr_start
            )
            if not text.strip():
                logger.error("Document has no extractable text", document_id=document_id)
                record.status = "failed"
                record.stage = "no_text"
                record.progress_percent = 0
                await repo.save_document(record)
                return

            if record.file_type == "pdf" and not extract_pdf_text(file_path).strip():
                record.stage = "ocr_done"
                record.progress_percent = 40
                await repo.save_document(record)

            record.status = "indexing"
            record.stage = "indexing"
            record.progress_percent = 45
            await repo.save_document(record)

            chunk_pairs: list[tuple[str, str]] = []
            chunks: list[DocumentChunkRecord] = []
            for index, content in enumerate(split_text(text)):
                clause = guess_clause(content)
                chunk_pairs.append((content, clause))
                chunks.append(
                    DocumentChunkRecord(
                        id=f"chunk_{uuid.uuid4().hex[:10]}",
                        document_id=document_id,
                        chunk_index=index,
                        content=content,
                        source_clause=clause,
                        keywords_json=list({word for word in content.split() if len(word) >= 2})[:20],
                    )
                )
            await repo.replace_chunks(document_id, chunks)

            record.status = "qa_generating"
            record.stage = "qa_generating"
            record.progress_percent = 75
            await repo.save_document(record)

            from src.integrations.qa_extractor import build_qa_records, extract_qa_from_chunks

            qa_items = await extract_qa_from_chunks(chunk_pairs)
            qa_records = build_qa_records(document_id, qa_items)
            await repo.replace_qa(document_id, qa_records)
            logger.info(
                "Document QA generated",
                document_id=document_id,
                qa_count=len(qa_records),
            )

            record.status = "ready"
            record.stage = "ready"
            record.progress_percent = 100
            await repo.save_document(record)
        except Exception as exc:
            logger.error("Document indexing failed", document_id=document_id, error=str(exc))
            record.status = "failed"
            record.stage = "failed"
            record.progress_percent = 0
            await repo.save_document(record)


class RagService:
    QA_THRESHOLD = QA_DIRECT_THRESHOLD

    def __init__(self, repo: KnowledgeRepository):
        self.repo = repo
        self._provider = None

    @property
    def provider(self):
        if self._provider is None:
            self._provider = create_llm_provider()
        return self._provider

    async def search_test(self, query: str) -> SearchTestData:
        results: list[SearchTestResult] = []
        rows = await self.repo.list_all_qa_with_docs()
        for qa, _ in rows:
            score = max(text_similarity(query, qa.question), text_similarity(query, qa.answer))
            if score >= 0.35:
                results.append(
                    SearchTestResult(
                        type="qa",
                        question=qa.question,
                        answer=qa.answer,
                        similarity=round(score, 2),
                        source_clause=qa.source_clause,
                    )
                )
        results.sort(key=lambda item: item.similarity, reverse=True)
        return SearchTestData(results=results[:10])

    async def try_answer(self, user_content: str) -> dict | None:
        from src.integrations.llm_factory import is_policy_question

        if not is_policy_question(user_content):
            return None

        qa_hit = await self._search_qa(user_content)
        if qa_hit and qa_hit["similarity"] >= self.QA_THRESHOLD:
            qa, doc = qa_hit["qa"], qa_hit["doc"]
            content = qa.answer
            if not content.endswith("。"):
                content += "。"
            if doc:
                content = (
                    f"根据《{doc.filename.replace('.pdf', '').replace('.docx', '')}》"
                    f"{qa.source_clause}，{content}"
                )
            return {
                "content": content,
                "message_type": "text",
                "metadata": {
                    "sources": [
                        {
                            "document_id": qa.document_id,
                            "filename": doc.filename if doc else "",
                            "clause": qa.source_clause,
                        }
                    ]
                },
            }

        chunks = await self._retrieve_chunks(user_content)
        if not chunks:
            return None

        return await self._generate_with_context(user_content, chunks)

    async def _search_qa(self, query: str) -> dict | None:
        rows = await self.repo.list_all_qa_with_docs()
        best: dict | None = None
        best_score = 0.0
        for qa, doc in rows:
            score = max(text_similarity(query, qa.question), text_similarity(query, qa.answer))
            if score > best_score:
                best_score = score
                best = {"qa": qa, "doc": doc, "similarity": score}
        return best

    async def _retrieve_chunks(self, query: str, limit: int = 3) -> list[tuple[DocumentChunkRecord, DocumentRecord | None, float]]:
        chunks = await self.repo.list_chunks()
        scored: list[tuple[DocumentChunkRecord, DocumentRecord | None, float]] = []
        for chunk in chunks:
            doc = await self.repo.get_document(chunk.document_id)
            if doc is None or doc.status != "ready":
                continue
            score = text_similarity(query, chunk.content)
            if score >= 0.25:
                scored.append((chunk, doc, score))
        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:limit]

    async def _generate_with_context(
        self, user_content: str, chunks: list[tuple[DocumentChunkRecord, DocumentRecord | None, float]]
    ) -> dict:
        context_parts: list[str] = []
        sources: list[dict] = []
        for chunk, doc, _ in chunks:
            filename = doc.filename if doc else ""
            context_parts.append(f"[{filename} · {chunk.source_clause}]\n{chunk.content}")
            if doc:
                sources.append(
                    {
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "clause": chunk.source_clause,
                    }
                )

        system_prompt = (
            "你是企业差旅与报销政策问答助手。请仅依据提供的政策片段回答用户问题。\n"
            "要求：\n"
            "1. 回答准确简洁，涉及标准数字须与原文一致\n"
            "2. 若片段不足以回答，说明无法从现有政策中找到依据\n"
            "3. 不要重复自我介绍\n"
            "4. 多个要点请分段，使用「一、」「二、」格式\n"
        )
        context_block = "\n\n".join(context_parts)
        messages = [
            Message.system(system_prompt),
            Message.user(f"政策片段：\n{context_block}\n\n用户问题：{user_content}"),
        ]

        try:
            response = await self.provider.chat(messages, temperature=0.2, max_tokens=800)
            content = (response.content or "").strip()
        except Exception as exc:
            logger.error("RAG generation failed", error=str(exc))
            content = chunks[0][0].content[:300]

        if not content:
            content = chunks[0][0].content[:300]

        return {
            "content": content,
            "message_type": "text",
            "metadata": {"sources": sources},
        }
