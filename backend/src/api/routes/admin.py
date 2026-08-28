import csv
import io
import secrets
import time

from fastapi import Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_admin
from src.api.responses import error, paginated, success
from src.db.session import get_db
from src.models.admin import SystemConfigUpdate
from src.models.user import UserPublic
from src.repositories.session import MessageRepository, SessionRepository
from src.repositories.system_config import SystemConfigRepository
from src.services.admin import AdminConversationService, SystemConfigService

router = APIRouter(prefix="/api/admin", tags=["admin"])

_export_tokens: dict[str, dict] = {}
_TOKEN_TTL = 300


def _conversation_service(db: AsyncSession) -> AdminConversationService:
    return AdminConversationService(SessionRepository(db), MessageRepository(db))


def _config_service(db: AsyncSession) -> SystemConfigService:
    return SystemConfigService(SystemConfigRepository(db))


@router.get("/conversations/stats")
async def conversation_stats(
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    stats = await _conversation_service(db).get_stats()
    return success(stats.model_dump())


@router.get("/conversations/export")
async def export_conversations(
    keyword: str | None = Query(None),
    status: str | None = Query(None),
    session_ids: str | None = Query(None, description="逗号分隔的会话 ID，传入时仅导出选中项"),
    _: UserPublic = Depends(get_current_admin),
):
    ids_list = [x.strip() for x in session_ids.split(",") if x.strip()] if session_ids else None
    token = secrets.token_urlsafe(16)
    _export_tokens[token] = {
        "keyword": keyword,
        "status": status,
        "session_ids": ids_list,
        "expires": time.time() + _TOKEN_TTL,
    }
    return success({"download_url": f"/api/admin/conversations/export/file?token={token}"})


@router.get("/conversations/export/file")
async def export_conversations_file(
    token: str = Query(...),
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    payload = _export_tokens.get(token)
    if payload is None or payload["expires"] < time.time():
        return JSONResponse(status_code=404, content=error("导出链接已失效", code=404))

    session_ids = payload.get("session_ids")
    if session_ids:
        all_items, _ = await _conversation_service(db).list_conversations(None, None, 1, 10000)
        id_set = set(session_ids)
        items = [item for item in all_items if item.id in id_set]
    else:
        items, _ = await _conversation_service(db).list_conversations(
            payload.get("keyword"), payload.get("status"), 1, 10000
        )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["会话ID", "用户", "工号", "标题", "状态", "消息数", "创建时间", "更新时间"])
    for item in items:
        writer.writerow([
            item.id,
            item.user.display_name,
            item.user.employee_id,
            item.title,
            item.status,
            item.message_count,
            item.created_at,
            item.updated_at,
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=conversations.csv"},
    )


@router.get("/conversations")
async def list_conversations(
    keyword: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await _conversation_service(db).list_conversations(
        keyword, status, page, page_size
    )
    return paginated([item.model_dump() for item in items], total, page, page_size)


@router.get("/conversations/{session_id}")
async def get_conversation_detail(
    session_id: str,
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    detail = await _conversation_service(db).get_conversation_detail(session_id)
    if detail is None:
        return JSONResponse(status_code=404, content=error("会话不存在", code=404))
    return success(detail.model_dump())


@router.get("/settings")
async def get_settings(
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    config = await _config_service(db).get_config()
    return success(config.model_dump())


@router.put("/settings")
async def update_settings(
    body: SystemConfigUpdate,
    _: UserPublic = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    config = await _config_service(db).update_config(body)
    return success(config.model_dump())
