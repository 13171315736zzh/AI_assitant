import json

from fastapi import Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.api.responses import error, paginated, success
from src.db.session import get_db
from src.models.session import (
    BookingSelectionConfirm,
    MessageCreate,
    RoomSelectionConfirm,
    SessionCreate,
    SessionUpdate,
    PlanConfirm,
    EmailPlanConfirm,
    WorkpackageConfirm,
    WorkpackagePlanConfirm,
    LeavePlanConfirm,
    InfoCollectPlanConfirm,
    MeetingPlanConfirm,
)
from src.models.user import UserPublic
from src.repositories.session import MessageRepository, SessionRepository
from src.repositories.user import UserRepository
from src.repositories.user_settings import UserSettingsRepository
from src.services.session import SessionService
from src.services.settings import SettingsService

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _service(db: AsyncSession) -> SessionService:
    user_repo = UserRepository(db)
    return SessionService(
        SessionRepository(db),
        MessageRepository(db),
        settings_service=SettingsService(UserSettingsRepository(db), user_repo),
    )


async def _sse_stream(
    user_id: int,
    session_id: str,
    content: str,
    db: AsyncSession,
    *,
    card_draft: dict | None = None,
):
    svc = _service(db)
    async for event_type, payload in svc.stream_reply(
        user_id, session_id, content, card_draft=card_draft
    ):
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


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    deleted = await svc.delete_session(current_user.id, session_id)
    if not deleted:
        return JSONResponse(status_code=404, content=error("会话不存在", code=404))
    return success({"deleted": True})


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
    user_message, assistant_message, session_title = result
    return success(
        {
            "user_message": user_message.model_dump(),
            "assistant_message": assistant_message.model_dump(),
            "session_title": session_title,
        }
    )


@router.get("/{session_id}/stream")
async def stream_message(
    session_id: str,
    content: str = Query(..., min_length=1, max_length=8000),
    card_draft: str | None = Query(default=None, max_length=16000),
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    parsed_draft: dict | None = None
    if card_draft:
        try:
            parsed_draft = json.loads(card_draft)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content=error("卡片草稿格式无效", code=400),
            )
    return StreamingResponse(
        _sse_stream(
            current_user.id,
            session_id,
            content,
            db,
            card_draft=parsed_draft,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}/booking-selection")
async def confirm_booking_selection(
    session_id: str,
    body: BookingSelectionConfirm,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.confirm_booking_selection(
        current_user.id,
        session_id,
        body.flight_no,
        body.train_no,
        body.hotel_name,
    )
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法确认预订，请重新选择方案", code=400),
        )
    if result == "ended":
        return JSONResponse(
            status_code=400,
            content=error("会话已结束，无法确认预订", code=400),
        )
    user_message, assistant_message, session_title = result
    return success(
        {
            "user_message": user_message.model_dump(),
            "assistant_message": assistant_message.model_dump(),
            "session_title": session_title,
        }
    )


@router.post("/{session_id}/travel-plan-confirm")
async def confirm_travel_plan(
    session_id: str,
    body: EmailPlanConfirm,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    card_draft = {
        "meta_key": "travel_plan_confirm",
        "payload": {
            key: value
            for key, value in {
                "origin": body.origin,
                "destination": body.destination,
                "start_date": body.start_date,
                "end_date": body.end_date,
                "purpose": body.purpose,
                "transport_mode": body.transport_mode,
                "transport_other": body.transport_other,
                "recipient": body.recipient,
                "cc": body.cc,
                "subject": body.subject,
                "body": body.body,
                "signature": body.signature,
            }.items()
            if value is not None
        },
    }
    result = await svc.confirm_travel_plan(
        current_user.id,
        session_id,
        supplementary_content=body.supplementary_content,
        recipient=body.recipient,
        cc=body.cc,
        subject=body.subject,
        body=body.body,
        signature=body.signature,
        origin=body.origin,
        destination=body.destination,
        start_date=body.start_date,
        end_date=body.end_date,
        purpose=body.purpose,
        transport_mode=body.transport_mode,
        transport_other=body.transport_other,
        card_draft=card_draft if card_draft["payload"] else None,
    )
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法确认安排，请重试", code=400),
        )
    if result == "ended":
        return JSONResponse(
            status_code=400,
            content=error("会话已结束，无法确认", code=400),
        )
    user_message, assistant_message, session_title = result
    return success(
        {
            "user_message": user_message.model_dump(),
            "assistant_message": assistant_message.model_dump(),
            "session_title": session_title,
        }
    )


@router.post("/{session_id}/meeting-plan-confirm")
async def confirm_meeting_plan(
    session_id: str,
    body: MeetingPlanConfirm,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    card_draft = {
        "meta_key": "meeting_plan_confirm",
        "payload": {
            key: value
            for key, value in {
                "subject": body.subject,
                "room": body.room or body.selected_room,
                "selected_room": body.selected_room or body.room,
                "room_flexible": body.room_flexible,
                "attendees": body.attendees,
                "date_hint": body.date_hint,
                "start_hint": body.start_hint,
                "end_hint": body.end_hint,
            }.items()
            if value is not None
        },
    }
    result = await svc.confirm_meeting_plan(
        current_user.id,
        session_id,
        supplementary_content=body.supplementary_content,
        card_draft=card_draft if card_draft["payload"] else None,
    )
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法确认会议预约，请重试", code=400),
        )
    if result == "ended":
        return JSONResponse(
            status_code=400,
            content=error("会话已结束，无法确认", code=400),
        )
    user_message, assistant_message, session_title = result
    return success(
        {
            "user_message": user_message.model_dump(),
            "assistant_message": assistant_message.model_dump(),
            "session_title": session_title,
        }
    )


@router.post("/{session_id}/room-selection")
async def confirm_room_selection(
    session_id: str,
    body: RoomSelectionConfirm,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.confirm_room_selection(current_user.id, session_id, body.room)
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法确认会议室，请重新选择", code=400),
        )
    if result == "ended":
        return JSONResponse(
            status_code=400,
            content=error("会话已结束，无法确认预约", code=400),
        )
    user_message, assistant_message, session_title = result
    return success(
        {
            "user_message": user_message.model_dump(),
            "assistant_message": assistant_message.model_dump(),
            "session_title": session_title,
        }
    )


@router.post("/{session_id}/workpackage-plan-confirm")
async def confirm_workpackage_plan(
    session_id: str,
    body: WorkpackagePlanConfirm,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.confirm_workpackage_plan(
        current_user.id,
        session_id,
        project=body.project,
        all_days_eight_hours=body.all_days_eight_hours,
        hours_per_day=body.hours_per_day,
        supplementary_content=body.supplementary_content,
    )
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法确认工包填报信息，请重试", code=400),
        )
    if result == "ended":
        return JSONResponse(
            status_code=400,
            content=error("会话已结束，无法确认", code=400),
        )
    user_message, assistant_message, session_title = result
    return success(
        {
            "user_message": user_message.model_dump(),
            "assistant_message": assistant_message.model_dump(),
            "session_title": session_title,
        }
    )


@router.post("/{session_id}/workpackage-confirm")
async def confirm_workpackage(
    session_id: str,
    body: WorkpackageConfirm,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.confirm_workpackage(
        current_user.id, session_id, entries=body.entries
    )
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法确认工包填报，请重试", code=400),
        )
    if result == "ended":
        return JSONResponse(
            status_code=400,
            content=error("会话已结束，无法确认填报", code=400),
        )
    user_message, assistant_message, session_title = result
    return success(
        {
            "user_message": user_message.model_dump(),
            "assistant_message": assistant_message.model_dump(),
            "session_title": session_title,
        }
    )


@router.post("/{session_id}/leave-plan-confirm")
async def confirm_leave_plan(
    session_id: str,
    body: LeavePlanConfirm,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    card_draft = {
        "meta_key": "leave_plan_confirm",
        "payload": {
            key: value
            for key, value in {
                "leave_type": body.leave_type,
                "date_start": body.date_start,
                "date_end": body.date_end,
                "start_period": body.start_period,
                "end_period": body.end_period,
                "reason": body.reason,
                "attachment_name": body.attachment_name,
            }.items()
            if value is not None
        },
    }
    result = await svc.confirm_leave_plan(
        current_user.id,
        session_id,
        reason=body.reason,
        attachment_name=body.attachment_name,
        leave_type=body.leave_type,
        date_start=body.date_start,
        date_end=body.date_end,
        start_period=body.start_period,
        end_period=body.end_period,
        supplementary_content=body.supplementary_content,
        card_draft=card_draft if card_draft["payload"] else None,
    )
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法确认请假申请，请补充请假事由后重试", code=400),
        )
    if result == "ended":
        return JSONResponse(
            status_code=400,
            content=error("会话已结束，无法确认", code=400),
        )
    user_message, assistant_message, session_title = result
    return success(
        {
            "user_message": user_message.model_dump(),
            "assistant_message": assistant_message.model_dump(),
            "session_title": session_title,
        }
    )


@router.post("/{session_id}/info-collect-plan-confirm")
async def confirm_info_collect_plan(
    session_id: str,
    body: InfoCollectPlanConfirm,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    result = await svc.confirm_info_collect_plan(
        current_user.id,
        session_id,
        structured=body.structured,
        supplementary_content=body.supplementary_content,
    )
    if result is None:
        return JSONResponse(
            status_code=400,
            content=error("无法确认个人信息，请至少填写一项核心信息后重试", code=400),
        )
    if isinstance(result, tuple) and len(result) == 2 and result[0] == "validation_error":
        return JSONResponse(
            status_code=400,
            content=error(str(result[1]), code=400),
        )
    if result == "ended":
        return JSONResponse(
            status_code=400,
            content=error("会话已结束，无法确认", code=400),
        )
    user_message, assistant_message, session_title = result
    return success(
        {
            "user_message": user_message.model_dump(),
            "assistant_message": assistant_message.model_dump(),
            "session_title": session_title,
        }
    )
