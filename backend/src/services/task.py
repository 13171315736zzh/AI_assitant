from src.models.task import (
    TaskConfirmPublic,
    TaskPublic,
    TaskStatusPublic,
    TaskStepPublic,
)
from src.repositories.task import TaskRepository


def _to_task_public(record) -> TaskPublic:
    steps = [TaskStepPublic(**step) for step in (record.steps_json or [])]
    return TaskPublic(
        id=record.id,
        session_id=record.session_id,
        goal=record.goal,
        status=record.status,
        current_step=record.current_step,
        total_steps=record.total_steps,
        replan_count=record.replan_count,
        steps=steps,
        created_at=record.created_at.isoformat(),
    )


class TaskService:
    def __init__(self, task_repo: TaskRepository):
        self.task_repo = task_repo

    async def get_task(self, user_id: int, task_id: str) -> TaskPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None:
            return None
        return _to_task_public(record)

    async def cancel_task(self, user_id: int, task_id: str) -> TaskStatusPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None:
            return None
        if record.status in ("completed", "cancelled"):
            return TaskStatusPublic(id=record.id, status=record.status)
        updated = await self.task_repo.update(record, status="cancelled")
        return TaskStatusPublic(id=updated.id, status=updated.status)

    async def confirm_task(
        self, user_id: int, task_id: str, step_id: int, params: dict | None = None
    ) -> TaskConfirmPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None:
            return None
        if record.status == "cancelled":
            return None

        steps = list(record.steps_json or [])
        for step in steps:
            if step.get("step_id") == step_id:
                if params:
                    step["params"] = {**step.get("params", {}), **params}
                step["status"] = "running"
                break

        updated = await self.task_repo.update(
            record,
            status="running",
            current_step=step_id,
            steps_json=steps,
        )
        return TaskConfirmPublic(
            id=updated.id,
            status=updated.status,
            current_step=updated.current_step,
        )

    async def update_step_params(
        self, user_id: int, task_id: str, step_id: int, params: dict
    ) -> TaskPublic | None:
        record = await self.task_repo.get_by_id(task_id, user_id)
        if record is None:
            return None

        steps = list(record.steps_json or [])
        found = False
        for step in steps:
            if step.get("step_id") == step_id:
                step["params"] = {**step.get("params", {}), **params}
                found = True
                break
        if not found:
            return None

        updated = await self.task_repo.update(record, steps_json=steps)
        return _to_task_public(updated)
