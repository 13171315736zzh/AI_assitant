from fastapi import Depends
from fastapi.responses import JSONResponse
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.api.responses import error, success
from src.db.session import get_db
from src.models.form import FORM_TYPES, FormPreviewRequest, FormSubmitRequest
from src.models.user import UserPublic
from src.repositories.form import FormRepository
from src.services.form import FormService

router = APIRouter(prefix="/api/forms", tags=["forms"])


def _service(db: AsyncSession) -> FormService:
    return FormService(FormRepository(db))


@router.post("/{form_type}/preview")
async def preview_form(
    form_type: str,
    body: FormPreviewRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if form_type not in FORM_TYPES:
        return JSONResponse(status_code=404, content=error("表单类型不存在", code=404))
    svc = _service(db)
    form = await svc.preview(
        current_user.id,
        form_type,
        body.session_id,
        body.task_id,
        body.fields or None,
    )
    if form is None:
        return JSONResponse(status_code=404, content=error("表单类型不存在", code=404))
    return success(form.model_dump())


@router.get("/{form_id}/receipt")
async def get_receipt(
    form_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    receipt = await svc.get_receipt(current_user.id, form_id)
    if receipt is None:
        return JSONResponse(status_code=404, content=error("回执不存在", code=404))
    return success(receipt.model_dump())


@router.post("/{form_id}/confirm")
async def confirm_form(
    form_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.confirm(current_user.id, form_id)
    if result is None:
        return JSONResponse(status_code=404, content=error("表单不存在", code=404))
    return success(result.model_dump())


@router.post("/{form_id}/submit")
async def submit_form(
    form_id: str,
    body: FormSubmitRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.submit(current_user.id, form_id, body.fields)
    if result is None:
        return JSONResponse(status_code=404, content=error("表单不存在", code=404))
    return success(result.model_dump())


@router.get("/{form_id}")
async def get_form(
    form_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    form = await svc.get_form(current_user.id, form_id)
    if form is None:
        return JSONResponse(status_code=404, content=error("表单不存在", code=404))
    return success(form.model_dump())
