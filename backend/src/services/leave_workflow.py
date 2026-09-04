"""请假申请流程执行。"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.leave_workflow import (
    LeavePlan,
    apply_leave_plan_draft,
    build_execution_summary,
    build_leave_plan,
    build_leave_plan_confirm_content,
    build_leave_plan_confirm_metadata,
    build_task_metadata,
    compute_leave_days,
    format_leave_period,
    is_leave_plan_update,
    is_leave_workflow_intent,
    is_ready_to_execute,
    missing_slots,
)
from src.agent.session_context import extend_user_messages, has_pending_plan, load_session_context
from src.agent.workflow_plan import link_task_to_plan
from src.agent.workflow_queue import get_pending_workflow_queue
from src.agent.workflow_confirm import (
    get_pending_meta,
    is_meta_confirmed,
    mark_meta_confirmed,
    mark_meta_superseded,
)
from src.db.task_models import TaskRecord
from src.repositories.form import FormRepository
from src.repositories.session import MessageRepository
from src.repositories.task import TaskRepository
from src.repositories.user import UserRepository
from src.services.form import FormService


def _new_task_id() -> str:
    return f"task_{secrets.token_hex(4)}"


def _leave_card_payload(card_draft: dict | None) -> dict:
    if not card_draft or card_draft.get("meta_key") != "leave_plan_confirm":
        return {}
    payload = card_draft.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


class LeaveWorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.task_repo = TaskRepository(db)
        self.form_repo = FormRepository(db)
        self.user_repo = UserRepository(db)
        self.form_service = FormService(self.form_repo)

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
            self.message_repo, session_id, "leave_plan_confirm"
        )
        has_pending_plan_flag = has_pending_plan(pending_plan)

        queue = await get_pending_workflow_queue(self.message_repo, session_id)
        wp_pending, _ = await get_pending_meta(
            self.message_repo, session_id, "workpackage_plan_confirm"
        )
        wp_fill_pending, _ = await get_pending_meta(
            self.message_repo, session_id, "workpackage_confirm"
        )
        if "leave" in queue and (wp_pending or wp_fill_pending):
            return None

        if not is_leave_workflow_intent(ctx.combined_text):
            card_payload = _leave_card_payload(card_draft)
            if not (
                has_pending_plan_flag
                and (is_leave_plan_update(user_content) or card_payload)
            ):
                return None

        plan = build_leave_plan(ctx.user_messages)
        plan = apply_leave_plan_draft(plan, _leave_card_payload(card_draft))
        missing = missing_slots(plan)
        if missing and not has_pending_plan_flag:
            return (
                self._missing_slots_prompt(missing),
                "text",
                None,
            )

        if not is_ready_to_execute(plan):
            if has_pending_plan_flag:
                return (
                    "请补充请假的具体时间，例如「9月5日到9月7日」或「下周四请半天假」。",
                    "text",
                    None,
                )
            return None

        if await is_meta_confirmed(self.message_repo, session_id, "leave_plan_confirm"):
            return None

        if pending_plan_msg and has_pending_plan_flag:
            mark_meta_superseded(pending_plan_msg, "leave_plan_confirm")
            await self.db.flush()

        content = build_leave_plan_confirm_content(
            plan, updated=has_pending_plan_flag
        )
        metadata = build_leave_plan_confirm_metadata(plan)
        return content, "text", metadata

    async def confirm_leave_plan(
        self,
        user_id: int,
        session_id: str,
        *,
        reason: str | None = None,
        attachment_name: str | None = None,
        leave_type: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
        supplementary_content: str | None = None,
        card_draft: dict | None = None,
    ) -> tuple[str, str, dict] | None:
        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, "leave_plan_confirm"
        )
        if pending_msg is None or pending is None:
            return None

        ctx = await load_session_context(self.message_repo, session_id)
        user_messages = extend_user_messages(ctx.user_messages, supplementary_content)
        plan = build_leave_plan(user_messages)
        draft = _leave_card_payload(card_draft)
        if not draft:
            draft = {
                key: value
                for key, value in {
                    "leave_type": leave_type,
                    "date_start": date_start,
                    "date_end": date_end,
                    "start_period": start_period,
                    "end_period": end_period,
                    "reason": reason,
                    "attachment_name": attachment_name,
                }.items()
                if value is not None
            }
        elif pending:
            for key in (
                "leave_type",
                "date_start",
                "date_end",
                "start_period",
                "end_period",
                "reason",
                "attachment_name",
            ):
                if key not in draft and pending.get(key) is not None:
                    draft[key] = pending.get(key)
        plan = apply_leave_plan_draft(plan, draft)

        if not plan.reason:
            return None
        if not is_ready_to_execute(plan):
            return None

        mark_meta_confirmed(pending_msg, "leave_plan_confirm")
        await self.db.flush()

        return await self._create_task_reply(user_id, session_id, plan)

    async def _create_task_reply(
        self,
        user_id: int,
        session_id: str,
        plan: LeavePlan,
    ) -> tuple[str, str, dict]:
        task_id = _new_task_id()
        leave_days = compute_leave_days(plan)
        period_label = format_leave_period(plan)

        steps = [
            {
                "step_id": 1,
                "action": "请假申请",
                "tool": "leave_apply",
                "status": "running",
                "depends_on": [],
                "params": {
                    "leave_type": plan.leave_type or "",
                    "period": period_label,
                },
                "result": None,
            },
            {
                "step_id": 2,
                "action": "用户确认",
                "tool": "user_confirm",
                "status": "pending",
                "depends_on": [1],
                "params": {},
                "result": None,
            },
        ]

        task = TaskRecord(
            id=task_id,
            session_id=session_id,
            user_id=user_id,
            goal=plan.raw_goal[:500] or f"{plan.leave_type}申请",
            status="running",
            current_step=1,
            total_steps=2,
            replan_count=0,
            steps_json=steps,
            created_at=datetime.now(UTC),
        )
        await self.task_repo.create(task)

        leave_form = await self.form_service.preview(
            user_id,
            "leave",
            session_id,
            task_id,
            {
                "leave_type": plan.leave_type or "事假",
                "date_start": plan.date_start or "",
                "date_end": plan.date_end or "",
                "start_period": plan.start_period,
                "end_period": plan.end_period,
                "reason": plan.reason or "",
                "days": str(leave_days),
                "attachment_name": plan.attachment_name or "",
            },
        )
        if leave_form:
            for step in steps:
                if step["tool"] == "leave_apply":
                    step["status"] = "completed"
                    step["result"] = {
                        "form_id": leave_form.form_id,
                        "leave_type": plan.leave_type,
                        "date_start": plan.date_start,
                        "date_end": plan.date_end,
                        "start_period": plan.start_period,
                        "end_period": plan.end_period,
                        "reason": plan.reason,
                        "attachment_name": plan.attachment_name,
                        "days": leave_days,
                    }

        await self.task_repo.update(task, steps_json=steps, current_step=1)

        await link_task_to_plan(
            self.message_repo,
            session_id,
            task_id,
            category="leave",
        )

        content = build_execution_summary(plan, task_id)
        metadata = build_task_metadata(plan, task_id)
        return content, "task", metadata

    @staticmethod
    def _missing_slots_prompt(missing: list[str]) -> str:
        labels = "、".join(missing)
        return (
            f"好的，我来帮您办理请假。还需要您补充：**{labels}**。\n\n"
            "请说明请假的具体时间（如「9月5日到9月7日」「下周四请半天假」），"
            "以及请假事由。如有医院假条等证明材料，可在确认时上传附件（选填）。"
        )
