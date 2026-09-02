from pycore.core import get_logger

from src.agent.chat_plugin import ChatAgentPlugin, FALLBACK_REPLY
from src.agent.email_etiquette import build_email_writing_snippets
from src.agent.meeting_workflow import is_meeting_workflow_intent
from src.agent.policy_context import format_policy_snippets, is_travel_policy_context
from src.agent.slot_labels import emphasize_slot_labels
from src.agent.travel_policy_rules import (
    apply_travel_reminders,
    build_travel_rule_snippets,
    parse_travel_context,
)
from src.agent.travel_workflow import is_travel_workflow_intent
from src.agent.user_memory import position_to_travel_staff_level
from src.agent.workpackage_workflow import is_workpackage_workflow_intent
from src.repositories.knowledge import KnowledgeRepository
from src.repositories.session import MessageRepository
from src.services.knowledge import RagService

logger = get_logger()


def _should_skip_travel_policy(session_text: str, metadata: dict | None) -> bool:
    if metadata:
        for key in (
            "workpackage_confirm",
            "workpackage_plan_confirm",
            "meeting_plan_confirm",
            "room_selection",
        ):
            if metadata.get(key):
                return True
    if is_workpackage_workflow_intent(session_text):
        return True
    if is_meeting_workflow_intent(session_text) and not is_travel_workflow_intent(session_text):
        return True
    return False


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

    async def generate_session_title(self, user_messages: list[str]) -> str:
        return await self.plugin.generate_session_title(user_messages)

    async def _session_user_text(self, session_id: str, user_content: str) -> str:
        records = await self.message_repo.list_recent_for_context(session_id, 40)
        parts = [r.content.strip() for r in records if r.role == "user" and r.content.strip()]
        trimmed = user_content.strip()
        if trimmed and (not parts or parts[-1] != trimmed):
            parts.append(trimmed)
        return "\n".join(parts)

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
        skip_travel = _should_skip_travel_policy(session_text, metadata)
        travel_ctx = parse_travel_context(session_text)
        if not travel_ctx.staff_level and confirmed_position:
            travel_ctx.staff_level = position_to_travel_staff_level(confirmed_position)
        policy_excerpts = (
            await self.rag_service.find_policy_excerpts(session_text, content)
            if is_travel_policy_context(session_text) and not skip_travel
            else []
        )
        return await self._finalize_reply(
            session_text,
            content,
            message_type,
            metadata,
            travel_ctx,
            policy_excerpts,
            skip_travel_policy=skip_travel,
        )

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
            content = emphasize_slot_labels(content)
            metadata = dict(metadata) if metadata else None
            if metadata:
                metadata.pop("policy_reminders", None)
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
        travel_ctx = parse_travel_context(session_text)
        if not travel_ctx.staff_level and confirmed_position:
            travel_ctx.staff_level = position_to_travel_staff_level(confirmed_position)
        policy_excerpts = (
            await self.rag_service.find_policy_excerpts(session_text)
            if is_travel_policy_context(session_text)
            else []
        )
        rule_snippets = build_travel_rule_snippets(travel_ctx)
        email_snippets = build_email_writing_snippets(session_text)
        policy_snippets = (
            format_policy_snippets(policy_excerpts)
            + rule_snippets
            + email_snippets
            + (memory_snippets or "")
        )

        rag = await self.rag_service.try_answer(user_content)
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
