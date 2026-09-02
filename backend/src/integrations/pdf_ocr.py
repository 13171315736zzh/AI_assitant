import base64
from pathlib import Path

import httpx
from openai import AsyncOpenAI
from pycore.core import get_logger

from src.config.settings import get_settings

logger = get_logger()

OCR_SYSTEM = (
    "你是 OCR 助手。请逐字输出图片中的中文政策文本，保留章节条款编号与数字，"
    "不要添加解释或 Markdown。"
)


async def ocr_pdf_to_text(
    file_path: Path,
    max_pages: int = 20,
    on_page_done=None,
) -> str:
    """扫描版 PDF：渲染为图片后调用 DashScope 视觉模型识别文字。"""
    settings = get_settings()
    if not settings.llm_api_key:
        logger.warning("PDF OCR skipped: llm_api_key not configured")
        return ""

    try:
        import fitz
    except ImportError:
        logger.warning("pymupdf not installed, skip PDF OCR")
        return ""

    doc = fitz.open(str(file_path))
    page_count = min(len(doc), max_pages)
    if page_count == 0:
        doc.close()
        return ""

    vision_model = settings.llm_vision_model or "qwen-vl-plus"
    http_client = httpx.AsyncClient(trust_env=False, timeout=float(settings.llm_timeout_seconds))
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        http_client=http_client,
        max_retries=0,
    )

    parts: list[str] = []
    try:
        for index in range(page_count):
            page = doc[index]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6))
            img_b64 = base64.b64encode(pix.tobytes("png")).decode()
            response = await client.chat.completions.create(
                model=vision_model,
                messages=[
                    {"role": "system", "content": OCR_SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                            },
                            {
                                "type": "text",
                                "text": f"请识别这份政策文档第 {index + 1} 页的全部文字。",
                            },
                        ],
                    },
                ],
                max_tokens=2500,
                temperature=0.1,
            )
            text = (response.choices[0].message.content or "").strip()
            if text:
                parts.append(text)
            logger.info("PDF OCR page done", page=index + 1, chars=len(text))
            if on_page_done:
                await on_page_done(index + 1, page_count)
    except Exception as exc:
        logger.error("PDF OCR failed", error=str(exc))
    finally:
        doc.close()
        await http_client.aclose()

    combined = "\n\n".join(parts)
    logger.info("PDF OCR finished", pages=page_count, total_chars=len(combined))
    return combined
