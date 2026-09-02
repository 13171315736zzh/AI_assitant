"""工包/工时填报流程执行。"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.workflow_confirm import get_pending_meta, is_meta_confirmed, mark_meta_confirmed
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
    is_ready_to_execute,
    is_workpackage_workflow_intent,
    needs_project_selection,
    normalize_workpackage_plan,
)
from src.db.task_models import TaskRecord
from src.integrations.mock_timesheet_provider import query_weekly_fill_plan
from src.repositories.form import FormRepository
from src.repositories.session import MessageRepository
from src.repositories.task import TaskRepository
from src.repositories.user import UserRepository
from src.repositories.user_settings import UserSettingsRepository
from src.services.form import FormService


def _new_task_id() -> str:
    return f"task_{secrets.token_hex(4)}"


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

        return options

    async def _build_plan(self, history, user_id: int) -> WorkpackagePlan:
        plan = normalize_workpackage_plan(build_workpackage_plan(history))
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
        )
        return snapshot.to_public_dict()

    async def try_execute(
        self,
        user_id: int,
        session_id: str,
        user_content: str,
    ) -> tuple[str, str, dict] | None:
        history = await self.message_repo.list_recent_for_context(session_id, limit=40)
        from types import SimpleNamespace

        full_history = list(history) + [SimpleNamespace(role="user", content=user_content)]
        combined = " ".join(m.content for m in full_history if m.role == "user")
        if not is_workpackage_workflow_intent(combined):
            return None

        plan = await self._build_plan(full_history, user_id)
        if not plan.fill_days and plan.period_hint != "本周":
            return None
        if plan.period_hint != "本周" and not plan.project and not plan.project_options:
            return None

        pending_plan_msg, pending_plan = await get_pending_meta(
            self.message_repo, session_id, "workpackage_plan_confirm"
        )
        if pending_plan_msg and pending_plan:
            return (
                "👇 请核对工时填报信息并点击「确认开始办理」。",
                "text",
                {"interactive": True, "workpackage_plan_confirm": pending_plan},
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
            if plan.period_hint == "本周" or needs_project_selection(plan):
                content = build_workpackage_plan_confirm_content(plan)
                metadata = build_workpackage_plan_confirm_metadata(plan)
                return content, "text", metadata
            if not is_ready_to_execute(plan):
                return None
            content = build_workpackage_plan_confirm_content(plan)
            metadata = build_workpackage_plan_confirm_metadata(plan)
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
    ) -> tuple[str, str, dict] | None:
        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, "workpackage_plan_confirm"
        )
        if pending_msg is None or pending is None:
            return None

        history = await self.message_repo.list_recent_for_context(session_id, limit=40)
        plan = await self._build_plan(history, user_id)

        selected = (project or pending.get("selected_project") or plan.project or "").strip()
        if not selected:
            options = pending.get("project_options") or plan.project_options
            if len(options) == 1:
                selected = options[0]
        if not selected:
            return None
        plan.project = selected

        if pending_msg.metadata_json:
            meta = dict(pending_msg.metadata_json)
            confirm = dict(meta.get("workpackage_plan_confirm") or {})
            confirm["selected_project"] = selected
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

        history = await self.message_repo.list_recent_for_context(session_id, limit=40)
        plan = await self._build_plan(history, user_id)
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

        content = build_execution_summary(plan, task_id, fill_plan)
        metadata = build_task_metadata(plan, task_id)
        return content, "task", metadata

    async def _mark_confirmed(self, message_record) -> None:
        meta = dict(message_record.metadata_json or {})
        confirm = dict(meta.get("workpackage_confirm") or {})
        confirm["status"] = "confirmed"
        meta["workpackage_confirm"] = confirm
        message_record.metadata_json = meta
        await self.db.flush()
