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
from src.agent.policy_context import (
    build_policy_search_query,
    format_policy_snippets,
    is_travel_policy_context,
    should_show_policy_with_question,
    trim_excerpt,
)
from src.agent.travel_policy_rules import parse_travel_context
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

    async def get_document_file(
        self, document_id: str, filename: str | None = None
    ) -> tuple[Path, str, str] | None:
        record = await self.repo.find_document_for_source(document_id, filename)
        if record is None:
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

        async def _persist_progress() -> None:
            await repo.save_document(record)
            await db.commit()

        try:
            record.status = "parsing"
            record.stage = "parsing"
            record.progress_percent = 20
            await _persist_progress()

            file_path = Path(record.file_path)

            async def _mark_ocr_start() -> None:
                record.status = "parsing"
                record.stage = "ocr"
                record.progress_percent = 30
                await _persist_progress()

            async def _mark_ocr_page(page: int, total: int) -> None:
                record.status = "parsing"
                record.stage = f"ocr:{page}/{total}"
                # OCR 阶段占 30%–40%
                record.progress_percent = 30 + int((page / max(total, 1)) * 10)
                await _persist_progress()

            text = await extract_document_text_async(
                file_path,
                record.file_type,
                on_ocr_start=_mark_ocr_start,
                on_ocr_page=_mark_ocr_page,
            )
            if not text.strip():
                logger.error("Document has no extractable text", document_id=document_id)
                record.status = "failed"
                record.stage = "no_text"
                record.progress_percent = 0
                await _persist_progress()
                return

            from src.agent.travel_policy_rules import discover_rule_ids_from_text

            if "差旅" in text or "出差" in text:
                discovered = discover_rule_ids_from_text(text)
                if discovered:
                    logger.info(
                        "Travel policy rules discovered in document",
                        document_id=document_id,
                        rules=discovered,
                    )

            if record.file_type == "pdf" and not extract_pdf_text(file_path).strip():
                record.stage = "ocr_done"
                record.progress_percent = 40
                await _persist_progress()

            record.status = "indexing"
            record.stage = "indexing"
            record.progress_percent = 45
            await _persist_progress()

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
            await db.commit()

            record.status = "qa_generating"
            record.stage = "qa_generating"
            record.progress_percent = 75
            await _persist_progress()

            from src.integrations.qa_extractor import build_qa_records, extract_qa_from_chunks

            qa_items = await extract_qa_from_chunks(chunk_pairs)
            qa_records = build_qa_records(document_id, qa_items)
            await repo.replace_qa(document_id, qa_records)
            await db.commit()
            logger.info(
                "Document QA generated",
                document_id=document_id,
                qa_count=len(qa_records),
            )

            record.status = "ready"
            record.stage = "ready"
            record.progress_percent = 100
            await _persist_progress()
        except Exception as exc:
            logger.error("Document indexing failed", document_id=document_id, error=str(exc))
            record.status = "failed"
            record.stage = "failed"
            record.progress_percent = 0
            await _persist_progress()


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

    async def enrich_sources(self, metadata: dict | None) -> dict | None:
        if not metadata:
            return metadata
        sources = metadata.get("sources")
        if not isinstance(sources, list) or not sources:
            return metadata
        enriched: list[dict] = []
        for raw in sources:
            if not isinstance(raw, dict):
                continue
            doc = await self.repo.find_document_for_source(
                raw.get("document_id"), raw.get("filename")
            )
            item = dict(raw)
            if doc:
                item["document_id"] = doc.id
                item["filename"] = doc.filename
            if not item.get("excerpt") and item.get("document_id"):
                excerpt = await self._find_excerpt_for_source(
                    item.get("document_id"), item.get("clause"), item.get("filename")
                )
                if excerpt:
                    item["excerpt"] = excerpt
            enriched.append(item)
        return {**metadata, "sources": enriched}

    async def find_policy_excerpts(
        self, user_content: str, assistant_content: str = "", limit: int = 2
    ) -> list[dict]:
        ctx = parse_travel_context(user_content)
        query = build_policy_search_query(user_content, assistant_content)
        if ctx.trip_days and ctx.trip_days > 7:
            query = f"{query} 出差包干制 第二十九条 超过7天"
        if ctx.origin and ctx.destination:
            query = f"{query} {ctx.origin} {ctx.destination} 城市间交通 第十六条 住宿标准"
        chunks = await self._retrieve_chunks(query, limit=limit)
        if not chunks and query != user_content:
            chunks = await self._retrieve_chunks(user_content, limit=limit)
        results: list[dict] = []
        for chunk, doc, _ in chunks:
            if doc is None:
                continue
            results.append(self._chunk_to_source(chunk, doc))
        return results

    async def build_reply_metadata(
        self,
        user_content: str,
        assistant_content: str,
        metadata: dict | None,
        prefetched_excerpts: list[dict] | None = None,
        policy_reminders: list | None = None,
    ) -> dict | None:
        metadata = await self.enrich_sources(metadata)
        sources = list((metadata or {}).get("sources") or [])

        if policy_reminders:
            doc_name = "国能数智科技开发（北京）有限公司差旅费管理实施细则（试行）.pdf"
            from src.agent.travel_policy_rules import reminders_to_sources

            sources.extend(reminders_to_sources(policy_reminders, doc_name))

        if should_show_policy_with_question(user_content, assistant_content) or policy_reminders:
            excerpts = prefetched_excerpts or await self.find_policy_excerpts(
                user_content, assistant_content
            )
            if excerpts:
                sources.extend(excerpts)

        if not sources:
            return metadata
        metadata = dict(metadata or {})
        metadata["sources"] = self._dedupe_sources(sources)
        if policy_reminders:
            metadata["policy_reminders"] = [
                {
                    "rule_id": item.rule_id,
                    "title": item.title,
                    "message": item.message,
                    "clause": item.clause,
                }
                for item in policy_reminders
            ]
        return metadata

    def _chunk_to_source(self, chunk, doc) -> dict:
        return {
            "document_id": doc.id,
            "filename": doc.filename,
            "clause": chunk.source_clause,
            "excerpt": trim_excerpt(chunk.content),
        }

    async def _find_excerpt_for_source(
        self, document_id: str | None, clause: str | None, filename: str | None
    ) -> str | None:
        chunks = await self.repo.list_chunks(document_id)
        if not chunks and filename:
            doc = await self.repo.find_document_for_source(document_id, filename)
            if doc:
                chunks = await self.repo.list_chunks(doc.id)
        if not chunks:
            return None
        if clause:
            for chunk in chunks:
                if clause in (chunk.source_clause or "") or clause in chunk.content:
                    return trim_excerpt(chunk.content)
        return trim_excerpt(chunks[0].content)

    @staticmethod
    def _dedupe_sources(sources: list[dict]) -> list[dict]:
        seen: set[str] = set()
        unique: list[dict] = []
        for item in sources:
            key = f"{item.get('document_id')}::{item.get('clause')}::{item.get('excerpt', '')[:40]}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

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
                            "excerpt": trim_excerpt(qa.answer),
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
                sources.append(self._chunk_to_source(chunk, doc))

        system_prompt = (
            "你是企业差旅与报销政策问答助手。请仅依据提供的政策片段回答用户问题。\n"
            "要求：\n"
            "1. 回答准确简洁，涉及标准数字须与原文一致\n"
            "2. 若片段不足以回答，说明无法从现有政策中找到依据\n"
            "3. 不要重复自我介绍\n"
            "4. 多个要点请分段，使用「一、」「二、」格式\n"
            "5. 若需用户确认职级、目的地等以适用差旅标准，须先引用政策原文中的具体标准数值，再提出追问\n"
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
