"""工作流节点取消确认与执行。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.task_catalog import infer_category
from src.agent.workflow_cancel import (
    CANCEL_META_KEY,
    MEETING_CANCEL_SELECTION_META_KEY,
    build_cancel_confirm_content,
    build_cancel_confirm_metadata,
    build_meeting_cancel_selection_content,
    build_meeting_cancel_selection_metadata,
    node_label,
    snapshot_to_items,
)
from src.agent.workflow_confirm import (
    get_pending_meta,
    mark_meta_confirmed,
    mark_meta_superseded,
)
from src.agent.workflow_plan import (
    _node_by_id,
    get_workflow_plan_from_session,
    mark_plan_node_cancelled,
)
from src.repositories.form import FormRepository
from src.repositories.session import MessageRepository
from src.repositories.task import TaskRepository
from src.services.task import (
    TaskService,
    _extract_gn_meeting_cancel_snapshot,
    _extract_hotel_booking_result,
    _extract_leave_result,
    _extract_room_booking_result,
    _extract_transport_booking_result,
    _extract_travel_apply_result,
    _extract_workpackage_result,
    _field_str,
    _find_apply_step,
    _form_id_from_step,
    _summarize_email_body,
    merge_cancel_snapshot,
)


_NODE_APPLY_TOOLS: dict[str, tuple[str, ...]] = {
    "room": ("meeting_book", "room_book"),
    "booking": ("flight_book",),
    "hotel": ("hotel_book",),
    "travel": ("travel_apply",),
    "workpackage": ("workpackage_fill",),
    "leave": ("leave_apply",),
    "gn_meeting": ("gn_meeting_book",),
    "email": ("email_notify",),
    "info_collect": ("info_collect_publish",),
}

_CATEGORY_TO_NODE: dict[str, str] = {
    "meeting": "room",
    "transport_book": "booking",
    "hotel_book": "hotel",
    "travel": "travel",
    "workpackage": "workpackage",
    "leave": "leave",
    "gn_meeting": "gn_meeting",
    "email": "email",
    "info_collect": "info_collect",
}


class WorkflowCancelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.task_repo = TaskRepository(db)
        self.form_repo = FormRepository(db)

    async def present_cancel_confirm(
        self,
        user_id: int,
        session_id: str,
        *,
        task_id: str | None = None,
        node_id: str | None = None,
        wf_plan: dict | None = None,
    ) -> tuple[str, str, dict] | None:
        if wf_plan is None:
            wf_plan = await get_workflow_plan_from_session(self.message_repo, session_id)

        resolved_node_id = node_id
        if not resolved_node_id and task_id:
            record = await self.task_repo.get_by_id(task_id, user_id)
            if record:
                resolved_node_id = _CATEGORY_TO_NODE.get(
                    infer_category(list(record.steps_json or []))
                )

        if not resolved_node_id:
            return ("未指定要取消的办理节点，请说明要取消哪一项。", "text", None)

        label = node_label(resolved_node_id)
        tid = await self._find_task_id(
            user_id, session_id, resolved_node_id, wf_plan, task_id
        )
        if not tid:
            return (
                f"未找到可取消的{label}。请先在办理流程中完成该项。",
                "text",
                None,
            )

        plan_node = _node_by_id(wf_plan, resolved_node_id) if wf_plan else None
        if plan_node and plan_node.get("status") == "cancelled":
            return (f"该{label}已取消，右侧节点已置灰。", "text", None)

        return await self._present_cancel_confirm_for_target(
            user_id,
            session_id,
            resolved_node_id,
            tid,
            wf_plan,
        )

    async def present_meeting_cancel_selection(
        self,
        user_id: int,
        session_id: str,
        wf_plan: dict | None = None,
    ) -> tuple[str, str, dict] | None:
        if wf_plan is None:
            wf_plan = await get_workflow_plan_from_session(self.message_repo, session_id)

        options = await self._collect_meeting_cancel_options(
            user_id, session_id, wf_plan
        )
        if not options:
            return ("未找到可取消的会议预约。请先在流程中完成国能会或会议室预约。", "text", None)

        if len(options) == 1:
            only = options[0]
            return await self._present_cancel_confirm_for_target(
                user_id,
                session_id,
                str(only["node_id"]),
                str(only["task_id"]),
                wf_plan,
            )

        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, MEETING_CANCEL_SELECTION_META_KEY
        )
        if pending_msg and pending:
            mark_meta_superseded(pending_msg, MEETING_CANCEL_SELECTION_META_KEY)
            await self.db.flush()

        return (
            build_meeting_cancel_selection_content(),
            "text",
            build_meeting_cancel_selection_metadata(options),
        )

    async def confirm_meeting_cancel_selection(
        self,
        user_id: int,
        session_id: str,
        node_ids: list[str],
    ) -> tuple[str, str, dict] | None:
        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, MEETING_CANCEL_SELECTION_META_KEY
        )
        if pending_msg is None or pending is None:
            return None

        available = {
            str(opt.get("node_id")): opt
            for opt in (pending.get("options") or [])
            if isinstance(opt, dict) and opt.get("node_id")
        }
        targets: list[dict[str, str]] = []
        for node_id in node_ids:
            opt = available.get(str(node_id))
            if opt and opt.get("task_id"):
                targets.append(
                    {"node_id": str(node_id), "task_id": str(opt["task_id"])}
                )

        if not targets:
            return None

        mark_meta_confirmed(pending_msg, MEETING_CANCEL_SELECTION_META_KEY)
        await self.db.flush()

        wf_plan = await get_workflow_plan_from_session(self.message_repo, session_id)
        first = targets[0]
        rest = targets[1:]
        return await self._present_cancel_confirm_for_target(
            user_id,
            session_id,
            first["node_id"],
            first["task_id"],
            wf_plan,
            cancel_queue=rest,
        )

    async def _present_cancel_confirm_for_target(
        self,
        user_id: int,
        session_id: str,
        node_id: str,
        task_id: str,
        wf_plan: dict | None,
        *,
        cancel_queue: list[dict[str, str]] | None = None,
        intro: str | None = None,
    ) -> tuple[str, str, dict] | None:
        label = node_label(node_id)
        plan_node = _node_by_id(wf_plan, node_id) if wf_plan else None
        if plan_node and plan_node.get("status") == "cancelled":
            return (f"该{label}已取消，右侧节点已置灰。", "text", None)

        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, CANCEL_META_KEY
        )
        if pending_msg and pending:
            mark_meta_superseded(pending_msg, CANCEL_META_KEY)
            await self.db.flush()

        snapshot = await self._collect_snapshot(user_id, task_id, node_id)
        if not snapshot:
            return (f"未找到{label}详情，请稍后重试。", "text", None)

        items = snapshot_to_items(node_id, snapshot)
        content = intro or build_cancel_confirm_content(label)
        metadata = build_cancel_confirm_metadata(
            node_id=node_id,
            node_label_text=label,
            task_id=task_id,
            items=items,
            cancel_queue=cancel_queue,
        )
        return content, "text", metadata

    async def confirm_cancel(
        self, user_id: int, session_id: str, task_id: str
    ) -> tuple[str, str, dict] | None:
        pending_msg, pending = await get_pending_meta(
            self.message_repo, session_id, CANCEL_META_KEY
        )
        if pending_msg is None or pending is None:
            return None
        if str(pending.get("task_id") or "") != str(task_id):
            return None

        node_id = str(pending.get("node_id") or "")
        label = str(pending.get("node_label") or node_label(node_id))

        mark_meta_confirmed(pending_msg, CANCEL_META_KEY)
        await self.db.flush()

        task_svc = TaskService(self.db)
        task = await task_svc.get_task(user_id, task_id)
        if task is None:
            return None

        if task.status == "completed":
            result = await task_svc.withdraw_oa_application(user_id, task_id)
            if result is None:
                return (
                    f"{label}已完成，暂无法自动取消。请在 OA 页面操作或联系行政协助。",
                    "text",
                    None,
                )
            content = f"已撤回{label} OA 申请并取消办理，右侧「{label}」节点已置灰。"
        else:
            result = await task_svc.cancel_task(
                user_id, task_id, plan_node_id=node_id or None
            )
            if result is None:
                return (f"取消{label}失败，请稍后重试。", "text", None)
            content = f"已取消{label}，右侧「{label}」节点已置灰。"

        if node_id:
            await mark_plan_node_cancelled(
                self.message_repo,
                session_id,
                node_id,
                task_id=task_id,
            )

        metadata: dict | None = None
        if result.assistant_message and isinstance(result.assistant_message, dict):
            metadata = dict(result.assistant_message.get("metadata") or {})

        fresh_plan = await get_workflow_plan_from_session(self.message_repo, session_id)
        if fresh_plan:
            metadata = dict(metadata or {})
            metadata["workflow_plan"] = fresh_plan

        queue = [
            item
            for item in (pending.get("cancel_queue") or [])
            if isinstance(item, dict) and item.get("node_id") and item.get("task_id")
        ]
        if queue:
            next_target = queue[0]
            remaining = queue[1:]
            next_node_id = str(next_target["node_id"])
            next_task_id = str(next_target["task_id"])
            next_label = node_label(next_node_id)
            next_snapshot = await self._collect_snapshot(
                user_id, next_task_id, next_node_id
            )
            if next_snapshot:
                next_items = snapshot_to_items(next_node_id, next_snapshot)
                next_meta = build_cancel_confirm_metadata(
                    node_id=next_node_id,
                    node_label_text=next_label,
                    task_id=next_task_id,
                    items=next_items,
                    cancel_queue=remaining or None,
                )
                if fresh_plan:
                    next_meta["workflow_plan"] = fresh_plan
                return (
                    f"已取消{label}。请确认是否取消以下{next_label}：",
                    "text",
                    next_meta,
                )

        return content, "text", metadata

    async def _collect_meeting_cancel_options(
        self,
        user_id: int,
        session_id: str,
        wf_plan: dict | None,
    ) -> list[dict[str, str | bool]]:
        options: list[dict[str, str | bool]] = []
        for node_id, label in (("gn_meeting", "国能会"), ("room", "会议室")):
            plan_node = _node_by_id(wf_plan, node_id) if wf_plan else None
            if plan_node and plan_node.get("status") == "cancelled":
                continue
            task_id = await self._find_task_id(
                user_id, session_id, node_id, wf_plan
            )
            if not task_id:
                continue
            options.append(
                {
                    "node_id": node_id,
                    "label": label,
                    "task_id": task_id,
                    "selected": True,
                }
            )
        return options

    async def _find_task_id(
        self,
        user_id: int,
        session_id: str,
        node_id: str,
        wf_plan: dict | None,
        explicit_task_id: str | None = None,
    ) -> str | None:
        if explicit_task_id:
            record = await self.task_repo.get_by_id(explicit_task_id, user_id)
            if record and record.session_id == session_id and record.status != "cancelled":
                return explicit_task_id

        plan_node = _node_by_id(wf_plan, node_id) if wf_plan else None
        if plan_node and plan_node.get("task_id"):
            tid = str(plan_node["task_id"])
            record = await self.task_repo.get_by_id(tid, user_id)
            if record and record.status != "cancelled":
                return tid

        messages = await self.message_repo.list_recent_for_context(session_id, limit=30)
        for record in reversed(messages):
            meta = record.metadata_json or {}
            task_id = meta.get("task_id")
            if not task_id:
                related = meta.get("related_tasks")
                if isinstance(related, list):
                    for item in related:
                        if not isinstance(item, dict):
                            continue
                        tid = item.get("task_id")
                        if not tid:
                            continue
                        if node_id == "room" and item.get("meeting_kind") == "room":
                            return str(tid)
                        if node_id == "gn_meeting" and item.get("meeting_kind") == "gn":
                            return str(tid)
                        if node_id == "booking" and item.get("booking_kind") == "transport":
                            return str(tid)
                        if node_id == "hotel" and item.get("booking_kind") == "hotel":
                            return str(tid)
                continue
            if record.message_type != "task":
                continue
            category = str(meta.get("category") or "")
            steps_desc = str(meta.get("steps_desc") or "")
            if self._message_matches_node(node_id, category, steps_desc):
                return str(task_id)

        tools = _NODE_APPLY_TOOLS.get(node_id, ())
        for task in await self.task_repo.list_all_by_user(user_id):
            if task.session_id != session_id or task.status == "cancelled":
                continue
            for step in task.steps_json or []:
                if step.get("tool") in tools:
                    return task.id
        return None

    @staticmethod
    def _message_matches_node(node_id: str, category: str, steps_desc: str) -> bool:
        checks: dict[str, tuple[str, ...]] = {
            "room": ("meeting", "会议室", "会议预约"),
            "gn_meeting": ("gn_meeting", "国能会"),
            "booking": ("transport_book", "交通", "机票", "车票"),
            "hotel": ("hotel_book", "酒店"),
            "travel": ("travel", "差旅", "出差"),
            "workpackage": ("workpackage", "工时", "工包"),
            "leave": ("leave", "请假"),
            "email": ("email", "邮件"),
            "info_collect": ("info_collect", "信息"),
        }
        tokens = checks.get(node_id, ())
        return category in tokens or any(token in steps_desc for token in tokens)

    async def _collect_snapshot(
        self, user_id: int, task_id: str, node_id: str
    ) -> dict[str, str] | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None:
            return None

        steps = list(record.steps_json or [])
        form_record = await self._load_form_record(user_id, steps)
        form_fields = (
            dict(form_record.fields_json)
            if form_record and form_record.fields_json
            else None
        )
        receipt_id = self._resolve_receipt_id(steps, form_record)
        category = infer_category(steps)

        if node_id == "room":
            snapshot = _extract_room_booking_result(steps, form_fields)
            return merge_cancel_snapshot(
                snapshot,
                await self._meeting_context_from_messages(
                    record.session_id, task_id, "room"
                ),
            )
        if node_id == "booking":
            return _extract_transport_booking_result(steps, form_fields, receipt_id)
        if node_id == "hotel":
            return _extract_hotel_booking_result(form_fields, receipt_id)
        if node_id == "travel":
            return _extract_travel_apply_result(form_fields, receipt_id)
        if node_id == "workpackage":
            return _extract_workpackage_result(form_fields, receipt_id)
        if node_id == "leave":
            return _extract_leave_result(form_fields, receipt_id)
        if node_id == "gn_meeting":
            snapshot = _extract_gn_meeting_cancel_snapshot(
                steps, form_fields, task_id
            )
            return merge_cancel_snapshot(
                snapshot,
                await self._meeting_context_from_messages(
                    record.session_id, task_id, "gn_meeting"
                ),
            )
        if node_id == "email":
            fields = form_fields or {}
            return {
                "recipient": _field_str(fields, "recipient"),
                "subject": _field_str(fields, "subject"),
                "body_summary": _summarize_email_body(fields.get("body")),
            }
        if node_id == "info_collect":
            fields = form_fields or {}
            return {
                "name": _field_str(fields, "name"),
                "employee_id": _field_str(fields, "employee_id"),
                "department": _field_str(fields, "department"),
                "base_location": _field_str(fields, "base_location"),
            }

        from src.agent.task_catalog import category_label

        return {
            "summary": record.goal or category_label(category),
            "task_title": record.goal or "—",
        }

    async def _meeting_context_from_messages(
        self,
        session_id: str,
        task_id: str,
        kind: str,
    ) -> dict[str, str]:
        context: dict[str, str] = {}
        messages = await self.message_repo.list_recent_for_context(session_id, limit=50)
        for record in reversed(messages):
            meta = record.metadata_json or {}
            if str(meta.get("task_id") or "") == task_id:
                if kind == "gn_meeting":
                    raw = meta.get("gn_meeting_result")
                    if isinstance(raw, dict):
                        context.update(
                            {str(k): str(v) for k, v in raw.items() if v is not None}
                        )
                if kind == "room":
                    raw = meta.get("room_booking_result")
                    if isinstance(raw, dict):
                        context.update(
                            {str(k): str(v) for k, v in raw.items() if v is not None}
                        )

            related = meta.get("related_tasks")
            if isinstance(related, list):
                for item in related:
                    if not isinstance(item, dict) or str(item.get("task_id")) != task_id:
                        continue
                    if kind == "gn_meeting" and item.get("meeting_kind") == "gn":
                        break
                    if kind == "room" and item.get("meeting_kind") == "room":
                        break

            plan = meta.get("meeting_plan_confirm")
            if not isinstance(plan, dict):
                continue
            if plan.get("subject"):
                context.setdefault("subject", str(plan["subject"]))
            if plan.get("attendees"):
                context.setdefault("attendees", str(plan["attendees"]))
            date_hint = str(plan.get("date_hint") or "").strip()
            start_hint = str(plan.get("start_hint") or "").strip()
            end_hint = str(plan.get("end_hint") or "").strip()
            if date_hint and start_hint:
                start_time = f"{date_hint} {start_hint}"
                end_time = f"{date_hint} {end_hint}" if end_hint else ""
                context.setdefault("start_time", start_time)
                if end_time:
                    context.setdefault("end_time", end_time)
                if "time_label" not in context:
                    context["time_label"] = (
                        f"{start_time} — {end_time}" if end_time else start_time
                    )
            elif start_hint and "time_label" not in context:
                time_value = start_hint
                if end_hint:
                    time_value = f"{start_hint} — {end_hint}"
                context.setdefault("time_label", time_value)
            if kind == "room" and plan.get("selected_room"):
                room = str(plan["selected_room"])
                if room and "room_name" not in context:
                    context["room_name"] = (
                        room if "会议室" in room else f"{room} 会议室"
                    )
        return context

    async def _load_form_record(self, user_id: int, steps: list[dict]):
        apply_step = _find_apply_step(steps)
        form_id = _form_id_from_step(apply_step)
        if not form_id:
            for step in steps:
                form_id = _form_id_from_step(step)
                if form_id:
                    break
        if not form_id:
            return None
        return await self.form_repo.get_by_id(str(form_id), user_id)

    @staticmethod
    def _resolve_receipt_id(steps: list[dict], form_record) -> str | None:
        if form_record is not None:
            receipt_id = str(getattr(form_record, "receipt_id", "") or "").strip()
            if receipt_id:
                return receipt_id
        for step in steps:
            result = step.get("result") or {}
            receipt_id = str(result.get("receipt_id") or "").strip()
            if receipt_id and receipt_id != "—":
                return receipt_id
        return None
