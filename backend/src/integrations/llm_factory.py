import httpx
import re
import types
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from pycore.core.exceptions import LLMError
from pycore.core.logger import get_logger
from pycore.integrations.llm.base import LLMConfig, Message
from pycore.integrations.llm.openai_provider import OpenAIProvider

from src.agent.prompts import ACK_SYSTEM, REJECT_MESSAGE, SYSTEM_PROMPT
from src.config.settings import AppSettings, get_settings

logger = get_logger()


def _build_openai_client(config: LLMConfig, http_client: httpx.AsyncClient) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        http_client=http_client,
        max_retries=0,
    )


def _patch_provider_chat(provider: OpenAIProvider, config: LLMConfig) -> None:
    """每次调用使用独立的 httpx 客户端，避免长连接在 uvicorn 中失效。"""

    original_chat = OpenAIProvider.chat
    original_stream = OpenAIProvider.chat_stream

    async def chat(
        self: OpenAIProvider,
        messages: list[Message],
        tools=None,
        **kwargs: Any,
    ):
        async with httpx.AsyncClient(trust_env=False, timeout=config.timeout) as http_client:
            self._client = _build_openai_client(config, http_client)
            try:
                return await original_chat(self, messages, tools, **kwargs)
            finally:
                self._client = None

    async def chat_stream(
        self: OpenAIProvider,
        messages: list[Message],
        tools=None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(trust_env=False, timeout=config.timeout) as http_client:
            self._client = _build_openai_client(config, http_client)
            try:
                async for token in original_stream(self, messages, tools, **kwargs):
                    yield token
            finally:
                self._client = None

    provider.chat = types.MethodType(chat, provider)  # type: ignore[method-assign]
    provider.chat_stream = types.MethodType(chat_stream, provider)  # type: ignore[method-assign]


def create_llm_provider(settings: AppSettings | None = None) -> OpenAIProvider:
    cfg = settings or get_settings()
    if not cfg.llm_api_key:
        logger.warning("LLM api key is empty; configure backend/config/app.toml llm_api_key")
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
    _patch_provider_chat(provider, llm_config)
    return provider


async def verify_llm_connection(settings: AppSettings | None = None) -> bool:
    cfg = settings or get_settings()
    if not cfg.llm_api_key:
        return False
    try:
        provider = create_llm_provider(cfg)
        await provider.chat([Message.user("ping")], max_tokens=8, temperature=0)
        return True
    except LLMError as exc:
        logger.error("LLM connectivity check failed", error=str(exc))
        return False


def build_llm_messages(
    history: list[Message],
    user_content: str,
    policy_snippets: str | None = None,
) -> list[Message]:
    reject_hint = f"\n\n若用户请求超出支持场景，请严格回复：{REJECT_MESSAGE}"
    system_extra = (policy_snippets or "") + reject_hint
    messages: list[Message] = [Message.system(SYSTEM_PROMPT + system_extra)]
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
