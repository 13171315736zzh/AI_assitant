import json

from fastapi import Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.api.responses import error, paginated, success
from src.db.session import get_db
from src.models.session import MessageCreate, SessionCreate, SessionUpdate
from src.models.user import UserPublic
from src.repositories.session import MessageRepository, SessionRepository
from src.services.session import SessionService

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _service(db: AsyncSession) -> SessionService:
    return SessionService(SessionRepository(db), MessageRepository(db))


async def _sse_stream(user_id: int, session_id: str, content: str, db: AsyncSession):
    svc = _service(db)
    async for event_type, payload in svc.stream_reply(user_id, session_id, content):
        if event_type == "error":
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            return
        yield f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("")
async def list_sessions(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    items, total = await svc.list_sessions(current_user.id, status, page, page_size)
    return paginated([i.model_dump() for i in items], total, page, page_size)


@router.post("")
async def create_session(
    body: SessionCreate,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    session = await svc.create_session(current_user.id, body.title)
    return success(session.model_dump())


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    session = await svc.get_session(current_user.id, session_id)
    if session is None:
        return JSONResponse(status_code=404, content=error("会话不存在", code=404))
    return success(session.model_dump())


@router.patch("/{session_id}")
async def update_session(
    session_id: str,
    body: SessionUpdate,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    session = await svc.update_session(
        current_user.id, session_id, body.status, body.ended_reason
    )
    if session is None:
        return JSONResponse(status_code=404, content=error("会话不存在", code=404))
    return success(session.model_dump())


@router.get("/{session_id}/messages")
async def list_messages(
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.list_messages(current_user.id, session_id, page, page_size)
    if result is None:
        return JSONResponse(status_code=404, content=error("会话不存在", code=404))
    items, total = result
    return paginated([m.model_dump() for m in items], total, page, page_size)


@router.post("/{session_id}/messages")
async def send_message(
    session_id: str,
    body: MessageCreate,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.send_message(current_user.id, session_id, body.content)
    if result is None:
        return JSONResponse(status_code=404, content=error("会话不存在", code=404))
    if result == "ended":
        return JSONResponse(
            status_code=400,
            content=error("会话已结束，无法发送新消息", code=400),
        )
    user_message, assistant_message = result
    return success(
        {
            "user_message": user_message.model_dump(),
            "assistant_message": assistant_message.model_dump(),
        }
    )


@router.get("/{session_id}/stream")
async def stream_message(
    session_id: str,
    content: str = Query(..., min_length=1, max_length=8000),
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return StreamingResponse(
        _sse_stream(current_user.id, session_id, content, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
