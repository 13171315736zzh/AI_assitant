from pycore.core import get_logger

from src.agent.chat_plugin import ChatAgentPlugin, FALLBACK_REPLY
from src.agent.email_etiquette import build_email_writing_snippets
from src.agent.policy_context import (
    format_policy_snippets,
    is_travel_policy_context,
    is_travel_reminder_eligible,
    should_skip_travel_reminders,
)
from src.agent.session_context import load_session_context
from src.agent.slot_labels import emphasize_slot_labels
from src.agent.travel_policy_rules import (
    apply_travel_reminders,
    build_travel_rule_snippets,
    parse_travel_context,
    strip_travel_reminder_blocks,
)
from src.agent.user_memory import position_to_travel_staff_level
from src.agent.workflow_plan import enrich_metadata_with_workflow_plan
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

    async def generate_session_title(self, user_messages: list[str]) -> str:
        return await self.plugin.generate_session_title(user_messages)

    async def _session_user_text(self, session_id: str, user_content: str) -> str:
        ctx = await load_session_context(
            self.message_repo, session_id, user_content=user_content
        )
        return ctx.merged_text

    async def generate_acks(self, session_id: str, user_content: str) -> list[str]:
        ctx = await load_session_context(
            self.message_repo, session_id, user_content=user_content
        )
        return await self.plugin.generate_acks(ctx)

    async def finalize_outgoing(
        self,
        session_id: str,
        user_content: str,
        content: str,
        message_type: str,
        metadata: dict | None,
        confirmed_position: str | None = None,
    ) -> tuple[str, str, dict | None]:
        session_text = await self._session_user_text(session_id, user_content)
        skip_travel = await should_skip_travel_reminders(
            self.message_repo,
            session_id,
            session_text,
            metadata,
        )
        travel_ctx = parse_travel_context(session_text)
        if not travel_ctx.staff_level and confirmed_position:
            travel_ctx.staff_level = position_to_travel_staff_level(confirmed_position)
        policy_excerpts = (
            await self.rag_service.find_policy_excerpts(session_text, content)
            if is_travel_reminder_eligible(session_text) and not skip_travel
            else []
        )
        content, message_type, metadata = await self._finalize_reply(
            session_text,
            content,
            message_type,
            metadata,
            travel_ctx,
            policy_excerpts,
            skip_travel_policy=skip_travel,
        )
        metadata = await enrich_metadata_with_workflow_plan(
            self.message_repo,
            session_id,
            metadata,
            session_text,
        )
        return content, message_type, metadata

    async def _finalize_reply(
        self,
        user_content: str,
        content: str,
        message_type: str,
        metadata: dict | None,
        travel_ctx,
        policy_excerpts: list[dict],
        skip_travel_policy: bool = False,
    ) -> tuple[str, str, dict | None]:
        if skip_travel_policy:
            content = strip_travel_reminder_blocks(content)
            content = emphasize_slot_labels(content)
            metadata = dict(metadata) if metadata else None
            if metadata:
                metadata.pop("policy_reminders", None)
                metadata.pop("sources", None)
            return content, message_type, metadata

        content, reminders = apply_travel_reminders(user_content, content, travel_ctx)
        content = emphasize_slot_labels(content)
        metadata = await self.rag_service.build_reply_metadata(
            user_content,
            content,
            metadata,
            policy_excerpts,
            policy_reminders=reminders,
        )
        return content, message_type, metadata

    async def generate_reply(
        self,
        session_id: str,
        user_content: str,
        memory_snippets: str = "",
        confirmed_position: str | None = None,
    ) -> tuple[str, str, dict | None]:
        session_text = await self._session_user_text(session_id, user_content)
        skip_travel = await should_skip_travel_reminders(
            self.message_repo,
            session_id,
            session_text,
            metadata=None,
        )
        travel_ctx = parse_travel_context(session_text)
        if not travel_ctx.staff_level and confirmed_position:
            travel_ctx.staff_level = position_to_travel_staff_level(confirmed_position)
        travel_eligible = is_travel_reminder_eligible(session_text) and not skip_travel
        policy_excerpts = (
            await self.rag_service.find_policy_excerpts(session_text)
            if travel_eligible
            else []
        )
        rule_snippets = build_travel_rule_snippets(travel_ctx) if travel_eligible else ""
        email_snippets = build_email_writing_snippets(session_text)
        policy_snippets = (
            format_policy_snippets(policy_excerpts)
            + rule_snippets
            + email_snippets
            + (memory_snippets or "")
        )

        rag = await self.rag_service.try_answer(session_text)
        if rag:
            return await self.finalize_outgoing(
                session_id,
                user_content,
                rag["content"],
                rag["message_type"],
                rag.get("metadata"),
                confirmed_position,
            )

        result = await self.plugin.execute(
            session_id=session_id,
            user_content=user_content,
            policy_snippets=policy_snippets or None,
        )
        if not result:
            logger.warning("Agent plugin failed")
            return FALLBACK_REPLY, "text", None
        data = result.data
        return await self.finalize_outgoing(
            session_id,
            user_content,
            data["content"],
            data["message_type"],
            data.get("metadata"),
            confirmed_position,
        )
