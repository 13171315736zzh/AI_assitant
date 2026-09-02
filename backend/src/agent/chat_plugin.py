from pycore.core import get_logger
from pycore.core.exceptions import LLMError
from pycore.plugins import BasePlugin, PluginResult

from pycore.integrations.llm.base import Message

from src.agent.prompts import ACK_SYSTEM, REJECT_MESSAGE, TITLE_SUMMARY_SYSTEM
from src.agent.session_title import clean_session_title, fallback_session_title
from src.agent.slot_labels import emphasize_slot_labels
from src.integrations.llm_factory import (
    build_llm_messages,
    build_policy_metadata,
    create_llm_provider,
    detect_message_type,
    history_from_records,
)
from src.repositories.session import MessageRepository

logger = get_logger()

FALLBACK_REPLY = "抱歉，AI 服务暂时不可用，请稍后重试或联系人工协助。"


class ChatAgentPlugin(BasePlugin):
    name: str = "chat_agent"
    description: str = "Generate assistant reply via DashScope LLM"
    parameters: dict = {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "user_content": {"type": "string"},
        },
        "required": ["session_id", "user_content"],
    }

    def __init__(self, message_repo: MessageRepository):
        super().__init__()
        self.message_repo = message_repo
        self._provider = None

    @property
    def provider(self):
        if self._provider is None:
            self._provider = create_llm_provider()
        return self._provider

    async def generate_session_title(self, user_messages: list[str]) -> str:
        if not user_messages:
            return fallback_session_title([])
        transcript = "\n".join(f"- {text.strip()}" for text in user_messages if text.strip())
        try:
            messages = [
                Message.system(TITLE_SUMMARY_SYSTEM),
                Message.user(f"用户发言：\n{transcript}"),
            ]
            response = await self.provider.chat(
                messages, max_tokens=48, temperature=0.2
            )
            title = clean_session_title(response.content or "")
            if title:
                return title
        except LLMError as exc:
            logger.error("Session title generation failed", error=str(exc))
        return fallback_session_title(user_messages)

    async def generate_acks(self, user_content: str) -> list[str]:
        try:
            messages = [Message.system(ACK_SYSTEM), Message.user(user_content)]
            response = await self.provider.chat(
                messages, max_tokens=160, temperature=0.3
            )
            content = (response.content or "").strip()
            if content:
                lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
                if lines:
                    return lines
        except LLMError as exc:
            logger.error("ACK generation failed", error=str(exc))
        return ["好的，我来处理您的请求。"]

    async def execute(self, session_id: str, user_content: str, **kwargs) -> PluginResult:
        try:
            policy_snippets = kwargs.get("policy_snippets")
            history_records = await self.message_repo.list_recent_for_context(session_id)
            history = history_from_records(history_records)
            messages = build_llm_messages(history, user_content, policy_snippets=policy_snippets)
            response = await self.provider.chat(messages)
            content = (response.content or "").strip()
            if not content:
                content = REJECT_MESSAGE
            content = emphasize_slot_labels(content)
            message_type = detect_message_type(content)
            metadata = build_policy_metadata(user_content, content)
            if metadata is None and message_type == "text":
                metadata = {"sources": []}
            return self.success(
                {
                    "content": content,
                    "message_type": message_type,
                    "metadata": metadata,
                }
            )
        except LLMError as exc:
            logger.error("LLM call failed", error=str(exc))
            self._provider = None
            return self.success(
                {
                    "content": FALLBACK_REPLY,
                    "message_type": "text",
                    "metadata": None,
                }
            )
        except Exception as exc:
            logger.error("Chat agent error", error=str(exc))
            return self.fail(str(exc))

    async def stream_tokens(self, session_id: str, user_content: str):
        history_records = await self.message_repo.list_recent_for_context(session_id)
        history = history_from_records(history_records)
        messages = build_llm_messages(history, user_content)
        async for token in self.provider.chat_stream(messages):
            yield token
