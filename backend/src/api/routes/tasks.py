from fastapi import Depends, Query
from fastapi.responses import JSONResponse
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.api.responses import error, paginated, success
from src.db.session import get_db
from src.models.task import EmailSentRequest, TaskConfirmRequest, TaskStepUpdateRequest
from src.models.user import UserPublic
from src.services.task import TaskService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _service(db: AsyncSession) -> TaskService:
    return TaskService(db)


@router.get("")
async def list_tasks(
    status: str | None = Query(None, description="running|completed|cancelled"),
    category: str | None = Query(
        None, description="travel|meeting|workpackage|email|other"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    items, total = await svc.list_tasks(
        current_user.id, page, page_size, status, category
    )
    return paginated([i.model_dump() for i in items], total, page, page_size)


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    task = await svc.get_task(current_user.id, task_id)
    if task is None:
        return JSONResponse(status_code=404, content=error("任务不存在", code=404))
    return success(task.model_dump())


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.cancel_task(current_user.id, task_id)
    if result is None:
        return JSONResponse(status_code=404, content=error("任务不存在", code=404))
    return success(result.model_dump())


@router.post("/{task_id}/confirm")
async def confirm_task(
    task_id: str,
    body: TaskConfirmRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.confirm_task(
        current_user.id, task_id, body.step_id, body.params or None
    )
    if result is None:
        return JSONResponse(status_code=404, content=error("任务不存在", code=404))
    return success(result.model_dump())


@router.patch("/{task_id}/steps/{step_id}")
async def update_task_step(
    task_id: str,
    step_id: int,
    body: TaskStepUpdateRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    task = await svc.update_step_params(
        current_user.id, task_id, step_id, body.params
    )
    if task is None:
        return JSONResponse(status_code=404, content=error("任务或步骤不存在", code=404))
    return success(task.model_dump())


@router.post("/{task_id}/email-sent")
async def confirm_email_sent(
    task_id: str,
    body: EmailSentRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.confirm_email_sent(
        current_user.id,
        task_id,
        recipient=body.recipient,
        subject=body.subject,
        message_id=body.message_id,
    )
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法确认邮件发送，请确认任务有效", code=400),
        )
    return success(result.model_dump())


@router.post("/{task_id}/oa-submit")
async def submit_oa_application(
    task_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.submit_oa_application(current_user.id, task_id)
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法提交 OA 申请，请确认任务与表单有效", code=400),
        )
    return success(result.model_dump())


@router.post("/{task_id}/oa-approve")
async def approve_oa_application(
    task_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.approve_oa_application(current_user.id, task_id)
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法完成 OA 审批，请确认任务与表单有效", code=400),
        )
    return success(result.model_dump())


@router.post("/{task_id}/gn-meeting-create")
async def create_gn_meeting(
    task_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.create_gn_meeting(current_user.id, task_id)
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法创建国能会议，请确认任务与表单有效", code=400),
        )
    return success(result.model_dump())
