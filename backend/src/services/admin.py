import secrets

from src.models.admin import (
    AdminConversationDetailPublic,
    AdminConversationPublic,
    ConversationExportPublic,
    ConversationMessagePreview,
    ConversationStatsPublic,
    ConversationUserPublic,
    SystemConfigPublic,
    SystemConfigUpdate,
)
from src.repositories.session import MessageRepository, SessionRepository
from src.repositories.system_config import DEFAULT_SYSTEM_CONFIG, SystemConfigRepository


class AdminConversationService:
    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
    ):
        self.session_repo = session_repo
        self.message_repo = message_repo

    async def get_stats(self) -> ConversationStatsPublic:
        total, active, today_new = await self.session_repo.get_stats()
        return ConversationStatsPublic(
            total_sessions=total,
            active_sessions=active,
            today_new_sessions=today_new,
        )

    async def list_conversations(
        self, keyword: str | None, status: str | None, page: int, page_size: int
    ) -> tuple[list[AdminConversationPublic], int]:
        rows, total = await self.session_repo.list_all_admin(keyword, status, page, page_size)
        items = [
            AdminConversationPublic(
                id=session.id,
                user=ConversationUserPublic(
                    display_name=user.display_name,
                    employee_id=user.employee_id,
                ),
                title=session.title,
                status=session.status,
                message_count=session.message_count,
                created_at=session.created_at.isoformat(),
                updated_at=session.updated_at.isoformat(),
            )
            for session, user in rows
        ]
        return items, total

    async def get_conversation_detail(
        self, session_id: str
    ) -> AdminConversationDetailPublic | None:
        from src.db.user_model import User
        from sqlalchemy import select

        session = await self.session_repo.get_by_id_admin(session_id)
        if session is None:
            return None

        db = self.session_repo.db
        result = await db.execute(select(User).where(User.id == session.user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        messages, _ = await self.message_repo.list_by_session(session_id, 1, 200)
        previews = [
            ConversationMessagePreview(
                role=msg.role if msg.role in ("user", "assistant") else "assistant",
                content=msg.content,
                created_at=msg.created_at.isoformat(),
            )
            for msg in messages
            if msg.role in ("user", "assistant")
        ]

        task_summary = None
        from sqlalchemy import select as sa_select
        from src.db.task_models import TaskRecord

        task_result = await db.execute(
            sa_select(TaskRecord).where(TaskRecord.session_id == session_id).limit(1)
        )
        task_row = task_result.scalar_one_or_none()
        if task_row:
            task_summary = (
                f"{task_row.goal} · {task_row.current_step}/{task_row.total_steps} 步骤"
            )

        return AdminConversationDetailPublic(
            id=session.id,
            user=ConversationUserPublic(
                display_name=user.display_name,
                employee_id=user.employee_id,
            ),
            title=session.title,
            status=session.status,
            message_count=session.message_count,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
            ended_reason=session.ended_reason,
            messages=previews,
            task_summary=task_summary,
        )

    async def export_conversations(
        self, keyword: str | None, status: str | None
    ) -> ConversationExportPublic:
        token = secrets.token_urlsafe(16)
        return ConversationExportPublic(
            download_url=f"/api/admin/conversations/export/file?token={token}"
        )


class SystemConfigService:
    def __init__(self, repo: SystemConfigRepository):
        self.repo = repo

    def _to_public(self, config: dict) -> SystemConfigPublic:
        merged = {**DEFAULT_SYSTEM_CONFIG, **config}
        return SystemConfigPublic(**merged)

    async def get_config(self) -> SystemConfigPublic:
        record = await self.repo.get()
        return self._to_public(record.config_json or {})

    async def update_config(self, body: SystemConfigUpdate) -> SystemConfigPublic:
        record = await self.repo.get()
        data = dict(record.config_json or DEFAULT_SYSTEM_CONFIG)
        for key, value in body.model_dump(exclude_unset=True).items():
            if value is not None:
                data[key] = value
        record.config_json = data
        await self.repo.save(record)
        return self._to_public(data)
