from pycore.core import get_logger

from src.agent.chat_plugin import ChatAgentPlugin, FALLBACK_REPLY
from src.repositories.knowledge import KnowledgeRepository
from src.repositories.session import MessageRepository
from src.services.knowledge import RagService

logger = get_logger()


class AgentService:
    def __init__(
        self,
        message_repo: MessageRepository,
        rag_service: RagService | None = None,
    ):
        self.message_repo = message_repo
        self.rag_service = rag_service or RagService(KnowledgeRepository(message_repo.db))
        self.plugin = ChatAgentPlugin(message_repo)

    async def generate_acks(self, user_content: str) -> list[str]:
        return await self.plugin.generate_acks(user_content)

    async def generate_reply(
        self, session_id: str, user_content: str
    ) -> tuple[str, str, dict | None]:
        rag = await self.rag_service.try_answer(user_content)
        if rag:
            return rag["content"], rag["message_type"], rag.get("metadata")

        result = await self.plugin.execute(session_id=session_id, user_content=user_content)
        if not result:
            logger.warning("Agent plugin failed")
            return FALLBACK_REPLY, "text", None
        data = result.data
        return data["content"], data["message_type"], data.get("metadata")
