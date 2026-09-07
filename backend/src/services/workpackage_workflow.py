"""工包/工时填报流程执行。"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.workflow_confirm import (
    get_pending_meta,
    is_meta_confirmed,
    mark_meta_confirmed,
    mark_meta_superseded,
)
from src.agent.workflow_plan import link_task_to_plan
from src.agent.workflow_queue import (
    attach_workflow_queue,
    detect_workflow_intents,
    get_pending_workflow_queue,
    multi_intent_preamble,
)
from src.agent.leave_workflow import (
    build_leave_plan,
    build_leave_plan_confirm_content,
    build_leave_plan_confirm_metadata,
    is_ready_to_execute as is_leave_ready_to_execute,
)
from src.agent.session_context import extend_user_messages, has_pending_plan, load_session_context, merge_user_texts
from src.agent.workpackage_workflow import (
    WorkpackagePlan,
    apply_project_options,
    build_execution_summary,
    build_task_metadata,
    build_workpackage_confirm_content,
    build_workpackage_confirm_metadata,
    build_workpackage_plan,
    build_workpackage_plan_confirm_content,
    build_workpackage_plan_confirm_metadata,
    can_auto_submit,
    has_resolved_period,
    is_ready_to_execute,
    is_workpackage_plan_update,
    is_workpackage_workflow_intent,
    needs_project_selection,
    normalize_workpackage_plan,
)
from src.db.task_models import TaskRecord
from src.integrations.mock_timesheet_provider import query_weekly_fill_plan
from src.repositories.form import FormRepository
from src.repositories.project_mapping import ProjectMappingRepository
from src.repositories.session import MessageRepository
from src.repositories.task import TaskRepository
from src.repositories.user import UserRepository
from src.repositories.user_settings import UserSettingsRepository
from src.services.form import FormService
from src.services.project_mapping import ProjectMappingService


def _new_task_id() -> str:
    return f"task_{secrets.token_hex(4)}"


def _workpackage_card_payload(card_draft: dict | None) -> dict:
    if not card_draft or card_draft.get("meta_key") != "workpackage_plan_confirm":
        return {}
    payload = card_draft.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _apply_workpackage_card(plan: WorkpackagePlan, payload: dict) -> None:
    """卡片非空字段覆盖对话/输入框解析结果。"""
    if not payload:
        return
    project = str(payload.get("project") or "").strip()
    if project:
        plan.project = project
    if payload.get("all_days_eight_hours") is True:
        plan.all_days_eight_hours = True
        plan.hours_per_day = 8.0
        plan.hours_confirmed = True
    elif payload.get("all_days_eight_hours") is False and payload.get("hours_per_day") is not None:
        plan.all_days_eight_hours = False
        plan.hours_per_day = float(payload["hours_per_day"])
        plan.hours_confirmed = True


class WorkpackageWorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.task_repo = TaskRepository(db)
        self.form_repo = FormRepository(db)
        self.user_repo = UserRepository(db)
        self.settings_repo = UserSettingsRepository(db)
        self.form_service = FormService(self.form_repo)

    async def _collect_project_options(self, user_id: int) -> list[str]:
        seen: set[str] = set()
        options: list[str] = []

        settings = await self.settings_repo.get_by_user_id(user_id)
        if settings:
            structured = settings.structured_json or {}
            for project in structured.get("related_projects") or []:
                name = str(project).strip()
                if name and name not in seen:
                    seen.add(name)
                    options.append(name)

        for task in await self.task_repo.list_all_by_user(user_id):
            for step in task.steps_json or []:
                if step.get("tool") != "workpackage_fill":
                    continue
                params = step.get("params") or {}
                project = str(params.get("project") or "").strip()
                if project and project not in seen:
                    seen.add(project)
                    options.append(project)
                result = step.get("result") or {}
                for entry in result.get("entries") or []:
                    entry_project = str(entry.get("project") or "").strip()
                    if entry_project and entry_project not in seen:
                        seen.add(entry_project)
                        options.append(entry_project)

        mapping_repo = ProjectMappingRepository(self.db)
        for mapping in await mapping_repo.list_all():
            project = (mapping.project_name or "").strip()
            if project and project not in seen:
                seen.add(project)
                options.append(project)

        return options

    async def _apply_project_mapping(self, plan: WorkpackagePlan, text: str) -> None:
        resolved = await ProjectMappingService(self.db).resolve_from_text(text)
        if resolved:
            plan.project = resolved.project_name
            plan.project_from_mapping = True

    async def _build_plan(self, user_messages, user_id: int) -> WorkpackagePlan:
        combined = merge_user_texts(
            [
                message.content.strip()
                for message in user_messages
                if getattr(message, "role", None) == "user" and message.content.strip()
            ]
        )
        plan = normalize_workpackage_plan(build_workpackage_plan(user_messages))
        await self._apply_project_mapping(plan, combined)
        options = await self._collect_project_options(user_id)
        return apply_project_options(plan, options)

    async def _query_fill_plan(self, plan: WorkpackagePlan) -> dict:
        snapshot = await query_weekly_fill_plan(
            plan.project or "项目",
            fill_days=plan.fill_days or 5.0,
            period_hint=plan.period_hint,
            date_start=plan.date_start,
            date_end=plan.date_end,
            hours_per_day=plan.hours_per_day,
            leave_slots=plan.leave_slots,
            full_week=plan.full_week,
        )
        plan.fill_days = snapshot.fillable_days
        return snapshot.to_public_dict()

    def _apply_multi_intent(
        self,
        content: str,
        metadata: dict | None,
        combined_text: str,
        *,
        active: str = "workpackage",
    ) -> tuple[str, dict]:
        intents = detect_workflow_intents(combined_text)
        meta = dict(metadata or {})
        preamble = multi_intent_preamble(intents)
        if preamble:
            content = f"{preamble}\n\n{content}"
        meta = attach_workflow_queue(meta, intents, active)
        return content, meta

    async def _maybe_chain_leave_confirm(
        self,
        session_id: str,
        content: str,
        metadata: dict,
    ) -> tuple[str, dict]:
        queue = await get_pending_workflow_queue(self.message_repo, session_id)
        if "leave" not in queue:
            return content, metadata

        ctx = await load_session_context(self.message_repo, session_id)
        leave_plan = build_leave_plan(ctx.user_messages)
        if not is_leave_ready_to_execute(leave_plan):
            return content, metadata

        leave_meta = build_leave_plan_confirm_metadata(leave_plan)
        leave_intro = build_leave_plan_confirm_content(leave_plan)
        merged = dict(metadata)
        merged.update(leave_meta)
        merged["interactive"] = True
        merged.pop("workflow_queue", None)
        chained_content = (
            f"{content}\n\n---\n\n接下来为您办理请假申请：\n\n"
            f"{leave_intro.split('：', 1)[-1]}"
        )
        return chained_content, merged

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
            self.message_repo, session_id, "workpackage_plan_confirm"
        )
        has_pending_plan_flag = has_pending_plan(pending_plan)
        card_payload = _workpackage_card_payload(card_draft)

        from src.agent.workflow_plan import (
            activated_plan_node,
            get_workflow_plan_from_session,
            is_parallel_workflow_plan,
            should_service_handle_activation,
        )

        wf_plan = await get_workflow_plan_from_session(self.message_repo, session_id)
        parallel_plan = is_parallel_workflow_plan(wf_plan)
        activated_workpackage = activated_plan_node(user_content, wf_plan) == "workpackage"
        if parallel_plan and not should_service_handle_activation(
            "workpackage", user_content, wf_plan
        ):
            return None

        if not is_workpackage_workflow_intent(ctx.combined_text):
            if not (
                activated_workpackage
                or (
                    has_pending_plan_flag
                    and (is_workpackage_plan_update(user_content) or card_payload)
                )
            ):
                return None

        plan = await self._build_plan(ctx.user_messages, user_id)
        _apply_workpackage_card(plan, card_payload)
        if plan.fill_days is None and not has_resolved_period(plan):
            if activated_workpackage:
                return (
                    "请说明要填报的项目与周期，例如「帮我在神东项目填本周5天工时」。",
                    "text",
                    None,
                )
            return None
        if not has_resolved_period(plan) and not plan.project and not plan.project_options:
            if activated_workpackage:
                return (
                    "请说明要填报的项目，例如「帮我在神东项目填本周5天工时」。",
                    "text",
                    None,
                )
            return None

        if can_auto_submit(plan):
            pending_fill_msg, _ = await get_pending_meta(
                self.message_repo, session_id, "workpackage_confirm"
            )
            if not has_pending_plan_flag and pending_fill_msg is None:
                fill_plan = await self._query_fill_plan(plan)
                if fill_plan.get("entries"):
                    return await self._create_task_reply(
                        user_id, session_id, plan, fill_plan
                    )

        plan_confirmed = await is_meta_confirmed(
            self.message_repo, session_id, "workpackage_plan_confirm"
        )

        pending_msg, pending_sel = await get_pending_meta(
            self.message_repo, session_id, "workpackage_confirm"
        )
        if plan_confirmed and pending_msg and pending_sel:
            return (
                "👇 请在下方勾选日期并确认工时填报计划。",
                "text",
                {"interactive": True, "workpackage_confirm": pending_sel},
            )

        if not plan_confirmed:
            if has_pending_plan_flag:
                mark_meta_superseded(pending_plan_msg, "workpackage_plan_confirm")
                await self.db.flush()
            if has_resolved_period(plan) or needs_project_selection(plan):
                content = build_workpackage_plan_confirm_content(
                    plan, updated=has_pending_plan_flag
                )
                metadata = build_workpackage_plan_confirm_metadata(plan)
                content, metadata = self._apply_multi_intent(
                    content, metadata, ctx.combined_text
                )
                return content, "text", metadata
            if not is_ready_to_execute(plan):
                return None
            content = build_workpackage_plan_confirm_content(
                plan, updated=has_pending_plan_flag
            )
            metadata = build_workpackage_plan_confirm_metadata(plan)
            content, metadata = self._apply_multi_intent(
                content, metadata, ctx.combined_text
            )
            return content, "text", metadata

        if await is_meta_confirmed(self.message_repo, session_id, "workpackage_confirm"):
            return None

        if not is_ready_to_execute(plan):
            return None

        fill_plan = await self._query_fill_plan(plan)
        content = build_workpackage_confirm_content(plan, fill_plan)
        metadata = build_workpackage_confirm_metadata(plan, fill_plan)
        return content, "text", metadata

    async def confirm_workpackage_plan(
        self,
        user_id: int,
        session_id: str,
        *,
        project: str | None = None,
        all_days_eight_hours: bool | None = None,
        hours_per_day: float | None = None,
        supplementary_content: str | None = None,
    ) -> tuple[str, str, dict] | None:
        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, "workpackage_plan_confirm"
        )
        if pending_msg is None or pending is None:
            return None

        ctx = await load_session_context(self.message_repo, session_id)
        user_messages = extend_user_messages(ctx.user_messages, supplementary_content)
        plan = await self._build_plan(user_messages, user_id)
        card_payload = {
            key: value
            for key, value in {
                "project": project,
                "all_days_eight_hours": all_days_eight_hours,
                "hours_per_day": hours_per_day,
            }.items()
            if value is not None
        }
        _apply_workpackage_card(plan, card_payload)

        selected = (plan.project or pending.get("selected_project") or "").strip()
        if not selected:
            options = pending.get("project_options") or plan.project_options
            if len(options) == 1:
                selected = options[0]
        if not selected:
            return None
        plan.project = selected

        if not plan.hours_confirmed:
            return None

        if pending_msg.metadata_json:
            meta = dict(pending_msg.metadata_json)
            confirm = dict(meta.get("workpackage_plan_confirm") or {})
            confirm["selected_project"] = selected
            confirm["hours_per_day"] = plan.hours_per_day
            confirm["hours_confirmed"] = plan.hours_confirmed
            confirm["all_days_eight_hours"] = plan.all_days_eight_hours
            confirm["items"] = build_workpackage_plan_confirm_metadata(plan)[
                "workpackage_plan_confirm"
            ]["items"]
            meta["workpackage_plan_confirm"] = confirm
            pending_msg.metadata_json = meta

        mark_meta_confirmed(pending_msg, "workpackage_plan_confirm")
        await self.db.flush()

        fill_plan = await self._query_fill_plan(plan)
        content = build_workpackage_confirm_content(plan, fill_plan)
        metadata = build_workpackage_confirm_metadata(plan, fill_plan)
        return content, "text", metadata

    async def confirm_workpackage(
        self,
        user_id: int,
        session_id: str,
        *,
        entries: list[dict] | None = None,
    ) -> tuple[str, str, dict] | None:
        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, "workpackage_confirm"
        )
        if pending_msg is None or pending is None:
            return None

        if not await is_meta_confirmed(
            self.message_repo, session_id, "workpackage_plan_confirm"
        ):
            return None

        ctx = await load_session_context(self.message_repo, session_id)
        plan = await self._build_plan(ctx.user_messages, user_id)
        pending_project = str(pending.get("project") or "").strip()
        if pending_project:
            plan.project = pending_project
        if not plan.project or not is_ready_to_execute(plan):
            return None

        raw_entries = entries if entries is not None else (pending.get("entries") or [])
        selected_entries = [
            entry for entry in raw_entries if entry.get("selected", True)
        ]
        if not selected_entries:
            return None

        fill_plan = {
            "project": plan.project,
            "period_label": pending.get("period_label"),
            "requested_days": pending.get("requested_days"),
            "fillable_days": pending.get("fillable_days"),
            "conflicts": pending.get("conflicts"),
            "entries": selected_entries,
        }

        await self._mark_confirmed(pending_msg)
        return await self._create_task_reply(user_id, session_id, plan, fill_plan)

    async def _create_task_reply(
        self,
        user_id: int,
        session_id: str,
        plan: WorkpackagePlan,
        fill_plan: dict,
    ) -> tuple[str, str, dict]:
        task_id = _new_task_id()
        entries = fill_plan.get("entries") or []
        total_hours = sum(e.get("hours", plan.hours_per_day) for e in entries)

        steps = [
            {
                "step_id": 1,
                "action": "工包填报",
                "tool": "workpackage_fill",
                "status": "running",
                "depends_on": [],
                "params": {
                    "project": plan.project or "",
                    "period": fill_plan.get("period_label", "本周"),
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
            goal=plan.raw_goal[:500] or f"{plan.project}工包填报",
            status="running",
            current_step=1,
            total_steps=2,
            replan_count=0,
            steps_json=steps,
            created_at=datetime.now(UTC),
        )
        await self.task_repo.create(task)

        wp_form = await self.form_service.preview(
            user_id,
            "workpackage",
            session_id,
            task_id,
            {
                "project": plan.project or "",
                "hours": str(int(total_hours)),
                "content": plan.content or f"{plan.project}相关工作",
                "period": fill_plan.get("period_label", "本周"),
            },
        )
        if wp_form:
            for step in steps:
                if step["tool"] == "workpackage_fill":
                    step["status"] = "completed"
                    step["result"] = {
                        "form_id": wp_form.form_id,
                        "entries": entries,
                        "total_hours": total_hours,
                        "total_person_days": sum(e.get("person_days", 0) for e in entries),
                    }

        await self.task_repo.update(task, steps_json=steps, current_step=1)

        await link_task_to_plan(
            self.message_repo,
            session_id,
            task_id,
            category="workpackage",
        )

        content = build_execution_summary(plan, task_id, fill_plan)
        metadata = build_task_metadata(plan, task_id)
        content, metadata = await self._maybe_chain_leave_confirm(
            session_id, content, metadata
        )
        return content, "task", metadata

    async def _mark_confirmed(self, message_record) -> None:
        meta = dict(message_record.metadata_json or {})
        confirm = dict(meta.get("workpackage_confirm") or {})
        confirm["status"] = "confirmed"
        meta["workpackage_confirm"] = confirm
        message_record.metadata_json = meta
        await self.db.flush()
