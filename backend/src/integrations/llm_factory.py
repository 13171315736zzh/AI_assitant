import httpx
import re

from openai import AsyncOpenAI

from pycore.core.exceptions import LLMError
from pycore.core.logger import get_logger
from pycore.integrations.llm.base import LLMConfig, Message
from pycore.integrations.llm.openai_provider import OpenAIProvider

from src.agent.prompts import ACK_SYSTEM, REJECT_MESSAGE, SYSTEM_PROMPT
from src.config.settings import AppSettings, get_settings

logger = get_logger()


def create_llm_provider(settings: AppSettings | None = None) -> OpenAIProvider:
    cfg = settings or get_settings()
    llm_config = LLMConfig(
        model=cfg.llm_model,
        api_key=cfg.llm_api_key,
        base_url=cfg.llm_base_url,
        temperature=cfg.llm_temperature,
        max_tokens=cfg.llm_max_tokens,
        timeout=float(cfg.llm_timeout_seconds),
        max_retries=2,
        retry_delay=1.0,
    )
    provider = OpenAIProvider(config=llm_config)
    http_client = httpx.AsyncClient(trust_env=False, timeout=llm_config.timeout)
    provider._client = AsyncOpenAI(
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
        http_client=http_client,
        max_retries=0,
    )
    return provider


def build_llm_messages(history: list[Message], user_content: str) -> list[Message]:
    reject_hint = f"\n\n若用户请求超出支持场景，请严格回复：{REJECT_MESSAGE}"
    messages: list[Message] = [Message.system(SYSTEM_PROMPT + reject_hint)]
    messages.extend(history)
    if (
        not history
        or history[-1].role != "user"
        or history[-1].content != user_content
    ):
        messages.append(Message.user(user_content))
    return messages


def history_from_records(records) -> list[Message]:
    items: list[Message] = []
    for record in records:
        if record.role not in ("user", "assistant"):
            continue
        if not record.content:
            continue
        if record.role == "user":
            items.append(Message.user(record.content))
        else:
            items.append(Message.assistant(record.content))
    return items


def detect_message_type(content: str) -> str:
    if REJECT_MESSAGE[:20] in content or content.strip().startswith("抱歉，我目前只能协助"):
        return "reject"
    return "text"


POLICY_DOC = {
    "document_id": "doc_001",
    "filename": "国家能源集团差旅管理办法2024修订版.pdf",
}

_POLICY_KEYWORDS = ("差旅", "住宿", "报销", "出差", "伙食", "交通", "标准", "政策", "制度", "规定", "鄂尔多斯")


def is_policy_question(user_content: str) -> bool:
    return any(kw in user_content for kw in _POLICY_KEYWORDS)


def _extract_clause(text: str) -> str:
    m = re.search(r"第[一二三四五六七八九十百]+章第[一二三四五六七八九十百]+条", text)
    if m:
        return m.group(0)
    m = re.search(r"第[一二三四五六七八九十百]+条", text)
    if m:
        return m.group(0)
    return "相关条款"


def build_policy_metadata(user_content: str, assistant_content: str) -> dict | None:
    if not is_policy_question(user_content):
        return None
    if detect_message_type(assistant_content) == "reject":
        return None
    return {
        "sources": [
            {
                **POLICY_DOC,
                "clause": _extract_clause(assistant_content),
            }
        ]
    }
