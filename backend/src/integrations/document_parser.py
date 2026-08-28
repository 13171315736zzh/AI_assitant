import re
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pycore.core import get_logger

logger = get_logger()

DOC_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_pdf_text(file_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("pypdf not installed, skip PDF text extraction")
        return ""
    try:
        reader = PdfReader(str(file_path))
        parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text.strip())
        return "\n".join(parts)
    except Exception as exc:
        logger.error("PDF extract failed", error=str(exc))
        return ""


def extract_docx_text(file_path: Path) -> str:
    try:
        with zipfile.ZipFile(file_path) as archive:
            xml_bytes = archive.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        texts: list[str] = []
        for node in root.iter(f"{DOC_NS}t"):
            if node.text:
                texts.append(node.text)
        return "".join(texts)
    except Exception as exc:
        logger.error("DOCX extract failed", error=str(exc))
        return ""


def extract_document_text(file_path: Path, file_type: str) -> str:
    if file_type == "pdf":
        return extract_pdf_text(file_path)
    if file_type == "docx":
        return extract_docx_text(file_path)
    return ""


async def extract_document_text_async(
    file_path: Path,
    file_type: str,
    on_ocr_start=None,
) -> str:
    text = extract_document_text(file_path, file_type)
    if text.strip() or file_type != "pdf":
        return text
    from src.integrations.pdf_ocr import ocr_pdf_to_text

    logger.info("PDF has no text layer, trying vision OCR", path=str(file_path))
    if on_ocr_start:
        await on_ocr_start()
    return await ocr_pdf_to_text(file_path)


def split_text(text: str, chunk_size: int = 400) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        if end < len(cleaned):
            split_at = cleaned.rfind("。", start, end)
            if split_at > start + chunk_size // 2:
                end = split_at + 1
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def guess_clause(text: str) -> str:
    for pattern in (
        r"第[一二三四五六七八九十百]+章第[一二三四五六七八九十百]+条",
        r"第[一二三四五六七八九十百]+条",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return "相关条款"


def new_document_id() -> str:
    return f"doc_{uuid.uuid4().hex[:8]}"
