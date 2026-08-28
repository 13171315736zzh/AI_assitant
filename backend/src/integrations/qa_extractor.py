import json
import re
import uuid

from pycore.core import get_logger
from pycore.integrations.llm.base import Message

from src.integrations.document_parser import guess_clause
from src.integrations.llm_factory import create_llm_provider

logger = get_logger()

QA_EXTRACT_SYSTEM = """你是政策文档分析助手。从给定政策片段中提取用户可能询问的问答对。

要求：
1. 每段提取 1-3 个高质量 QA；问题应自然（如「XX标准是多少？」），答案须准确引用原文关键信息
2. source_clause 标注条款（如「第三章第十二条」），无法确定则写「相关条款」
3. 只输出 JSON 数组，不要 markdown 或其他说明：
[{"question":"...","answer":"...","source_clause":"..."}]
"""


def _parse_qa_json(text: str) -> list[dict]:
    text = text.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [_normalize_qa_item(item) for item in data if isinstance(item, dict)]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return [_normalize_qa_item(item) for item in data if isinstance(item, dict)]
        except json.JSONDecodeError:
            pass
    return []


def _normalize_qa_item(item: dict) -> dict:
    question = str(item.get("question", "")).strip()
    answer = str(item.get("answer", "")).strip()
    clause = str(item.get("source_clause", "")).strip() or "相关条款"
    return {"question": question, "answer": answer, "source_clause": clause}


def _fallback_qa(content: str, clause: str) -> list[dict]:
    snippet = content.strip()
    if len(snippet) < 20:
        return []
    question = "该条款的主要内容是什么？"
    for kw in ("标准", "限额", "补助", "不得", "应当", "需要"):
        if kw in snippet:
            idx = snippet.find(kw)
            start = max(0, idx - 12)
            question = f"关于{snippet[start : idx + len(kw) + 8].strip('，。；')}的规定是什么？"
            break
    return [
        {
            "question": question[:80],
            "answer": snippet[:280],
            "source_clause": clause or guess_clause(snippet),
        }
    ]


async def extract_qa_from_chunks(chunks: list[tuple[str, str]]) -> list[dict]:
    """从 (content, source_clause) 列表提取 QA，LLM 失败时降级为规则兜底。"""
    provider = create_llm_provider()
    results: list[dict] = []
    seen_questions: set[str] = set()

    for content, clause in chunks:
        text = content.strip()
        if len(text) < 30:
            continue

        extracted: list[dict] = []
        try:
            response = await provider.chat(
                [
                    Message.system(QA_EXTRACT_SYSTEM),
                    Message.user(f"来源条款：{clause}\n\n政策片段：\n{text[:1500]}"),
                ],
                temperature=0.2,
                max_tokens=800,
            )
            extracted = _parse_qa_json(response.content or "")
        except Exception as exc:
            logger.warning("QA LLM extract failed", error=str(exc))

        if not extracted:
            extracted = _fallback_qa(text, clause)

        for item in extracted:
            q = item.get("question", "").strip()
            a = item.get("answer", "").strip()
            if not q or not a or q in seen_questions:
                continue
            seen_questions.add(q)
            results.append(
                {
                    "question": q,
                    "answer": a,
                    "source_clause": item.get("source_clause") or clause or guess_clause(text),
                }
            )

    return results[:30]


def build_qa_records(document_id: str, items: list[dict]) -> list:
    from src.db.knowledge_models import QARecord

    records: list[QARecord] = []
    for item in items:
        records.append(
            QARecord(
                id=f"qa_{uuid.uuid4().hex[:10]}",
                document_id=document_id,
                question=item["question"],
                answer=item["answer"],
                source_clause=item.get("source_clause") or "相关条款",
            )
        )
    return records
