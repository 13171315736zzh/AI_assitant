"""信息收集流程执行：写入用户长期记忆。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.info_collect_workflow import (
    PersonalInfoCollectPlan,
    build_execution_summary,
    build_info_collect_plan_confirm_content,
    build_info_collect_plan_confirm_metadata,
    build_personal_info_plan,
    is_info_collect_plan_update,
    is_info_collect_workflow_intent,
    is_ready_to_execute,
    missing_slots,
)
from src.agent.memory_validators import validate_structured_fields
from src.agent.memory_extractor import extract_structured_with_validation
from src.agent.session_context import extend_user_messages, has_pending_plan, load_session_context
from src.agent.workflow_card_merge import merge_confirmed_structured
from src.agent.workflow_confirm import (
    get_pending_meta,
    is_meta_confirmed,
    mark_meta_confirmed,
    mark_meta_superseded,
    try_reopen_confirmed_plan,
)
from src.models.settings import MemoryStructured, MemoryUpdateRequest
from src.repositories.session import MessageRepository
from src.repositories.user import UserRepository
from src.repositories.user_settings import UserSettingsRepository
from src.services.settings import SettingsService


def _card_payload(card_draft: dict[str, Any] | None, meta_key: str) -> dict[str, Any]:
    if not card_draft:
        return {}
    if card_draft.get("meta_key") and card_draft.get("meta_key") != meta_key:
        return {}
    payload = card_draft.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


class InfoCollectWorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.user_repo = UserRepository(db)
        self.settings_service = SettingsService(UserSettingsRepository(db), self.user_repo)

    async def try_execute(
        self,
        user_id: int,
        session_id: str,
        user_content: str,
        *,
        card_draft: dict | None = None,
    ) -> tuple[str, str, dict] | None:
        ctx = await load_session_context(
            self.message_repo, session_id, user_content=user_content
        )

        pending_plan_msg, pending_plan = await get_pending_meta(
            self.message_repo, session_id, "info_collect_plan_confirm"
        )
        has_pending_plan_flag = has_pending_plan(pending_plan)
        card_payload = _card_payload(card_draft, "info_collect_plan_confirm")

        from src.agent.workflow_plan import (
            activated_plan_node,
            get_workflow_plan_from_session,
            is_parallel_workflow_plan,
            should_service_handle_activation,
        )

        wf_plan = await get_workflow_plan_from_session(self.message_repo, session_id)
        activated_info = activated_plan_node(user_content, wf_plan) == "info_collect"
        if is_parallel_workflow_plan(wf_plan) and not should_service_handle_activation(
            "info_collect", user_content, wf_plan
        ):
            return None

        plan_confirmed = await is_meta_confirmed(
            self.message_repo, session_id, "info_collect_plan_confirm"
        )
        should_run = is_info_collect_workflow_intent(ctx.combined_text)
        if not should_run and has_pending_plan_flag:
            should_run = is_info_collect_plan_update(user_content) or bool(card_payload)
        if not should_run and plan_confirmed and is_info_collect_plan_update(user_content):
            should_run = True
        if not should_run and activated_info:
            should_run = True
        if not should_run:
            latest_extract = extract_structured_with_validation(
                user_content or ctx.latest_user_text
            )
            should_run = bool(latest_extract.updates or card_payload)
        if not should_run:
            return None

        existing = await self.settings_service.get_user_structured_memory(user_id)
        assistant_context = await self._assistant_context(session_id)
        plan = build_personal_info_plan(
            ctx.user_messages,
            existing,
            assistant_context=assistant_context,
        )
        card_structured = card_payload.get("structured")
        if isinstance(card_structured, dict):
            plan.structured = merge_confirmed_structured(
                dict(plan.structured),
                card_structured,
            )
        plan.structured = await self.settings_service._normalize_structured_fields(
            dict(plan.structured),
            source_text=ctx.combined_text,
        )
        validation_errors = validate_structured_fields(plan.structured)
        plan.field_errors = {**plan.field_errors, **validation_errors}

        if not is_ready_to_execute(plan):
            return (
                self._missing_slots_prompt(missing_slots(plan)),
                "text",
                None,
            )

        reopened = await try_reopen_confirmed_plan(
            self.message_repo,
            session_id,
            "info_collect_plan_confirm",
            user_content,
            is_update=is_info_collect_plan_update,
            can_present=is_ready_to_execute,
            build_content=build_info_collect_plan_confirm_content,
            build_metadata=build_info_collect_plan_confirm_metadata,
            plan=plan,
            pending_plan_msg=pending_plan_msg,
            has_pending_plan_flag=has_pending_plan_flag,
        )
        if reopened:
            await self.db.flush()
            return reopened

        if plan_confirmed:
            return None

        if pending_plan_msg and has_pending_plan_flag:
            mark_meta_superseded(pending_plan_msg, "info_collect_plan_confirm")
            await self.db.flush()

        content = build_info_collect_plan_confirm_content(
            plan, updated=has_pending_plan_flag
        )
        metadata = build_info_collect_plan_confirm_metadata(plan)
        return content, "text", metadata

    async def confirm_info_collect_plan(
        self,
        user_id: int,
        session_id: str,
        *,
        structured: dict | None = None,
        supplementary_content: str | None = None,
    ) -> tuple[str, str, dict] | None:
        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, "info_collect_plan_confirm"
        )
        if pending_msg is None or pending is None:
            return None

        existing = await self.settings_service.get_user_structured_memory(user_id)
        ctx = await load_session_context(self.message_repo, session_id)
        assistant_context = await self._assistant_context(session_id)
        user_messages = extend_user_messages(ctx.user_messages, supplementary_content)
        plan = build_personal_info_plan(
            user_messages,
            existing,
            assistant_context=assistant_context,
        )

        merged = merge_confirmed_structured(
            dict(plan.structured),
            structured,
            supplementary_text=supplementary_content or "",
        )
        plan = PersonalInfoCollectPlan(
            structured=merged,
            raw_goal=plan.raw_goal,
            field_errors=dict(plan.field_errors),
        )

        merge_text = ctx.combined_text
        if supplementary_content:
            merge_text = f"{merge_text}\n{supplementary_content.strip()}"

        plan.structured = await self.settings_service._normalize_structured_fields(
            dict(plan.structured),
            source_text=merge_text,
        )
        validation_errors = validate_structured_fields(plan.structured)
        plan.field_errors = {**plan.field_errors, **validation_errors}

        if not is_ready_to_execute(plan):
            return None

        if plan.field_errors:
            first_error = next(iter(plan.field_errors.values()))
            raise ValueError(first_error)

        mark_meta_confirmed(pending_msg, "info_collect_plan_confirm")
        await self.db.flush()

        await self.settings_service.update_memory(
            user_id,
            MemoryUpdateRequest(
                memory_enabled=True,
                structured=MemoryStructured.model_validate(plan.structured),
            ),
        )

        content = build_execution_summary(plan)
        return content, "text", None

    async def _assistant_context(self, session_id: str) -> str | None:
        records = await self.message_repo.list_recent_for_context(session_id, limit=6)
        for record in reversed(records):
            if record.role == "assistant" and record.content.strip():
                return record.content
        return None

    @staticmethod
    def _missing_slots_prompt(missing: list[str]) -> str:
        if not missing:
            missing = [
                "姓名",
                "性别",
                "身份证号",
                "工号",
                "岗位",
                "岗位类型",
                "常驻地（Base）",
                "部门",
                "邮箱",
                "交通偏好",
                "关联项目",
            ]
        labels = "、".join(missing)
        return (
            f"好的，我来帮您收集核心个人信息并写入长期记忆。当前还缺少：**{labels}**。\n\n"
            "请直接告诉我，例如：「我叫张明，工号 0176338，Base 北京，"
            "部门智能矿山事业部，邮箱 zhangming@company.com，交通偏好高铁，关联神东项目」。"
            "交通偏好可选：飞机、高铁、自驾、无偏好。"
        )
