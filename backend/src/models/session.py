from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SessionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    title: str
    status: str
    ended_reason: str | None
    message_count: int
    created_at: str
    updated_at: str


class SessionCreate(BaseModel):
    title: str = Field(default="新对话", max_length=128)


class SessionUpdate(BaseModel):
    status: str | None = None
    ended_reason: str | None = None


class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str
    message_type: str
    metadata: dict[str, Any] | None = None
    created_at: str


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)


class BookingSelectionConfirm(BaseModel):
    flight_no: str | None = None
    hotel_name: str | None = None


class RoomSelectionConfirm(BaseModel):
    room: str = Field(..., min_length=1, max_length=32)


class WorkpackagePlanConfirm(BaseModel):
    confirmed: bool = True
    project: str | None = Field(default=None, max_length=128)
    all_days_eight_hours: bool | None = None
    hours_per_day: float | None = Field(default=None, ge=0.5, le=24)
    supplementary_content: str | None = Field(default=None, max_length=8000)


class WorkpackageConfirm(BaseModel):
    confirmed: bool = True
    entries: list[dict[str, Any]] | None = None


class LeavePlanConfirm(BaseModel):
    confirmed: bool = True
    reason: str | None = Field(default=None, max_length=500)
    attachment_name: str | None = Field(default=None, max_length=256)
    leave_type: str | None = Field(default=None, max_length=32)
    date_start: str | None = Field(default=None, max_length=16)
    date_end: str | None = Field(default=None, max_length=16)
    start_period: str | None = Field(default=None, max_length=16)
    end_period: str | None = Field(default=None, max_length=16)
    supplementary_content: str | None = Field(default=None, max_length=8000)


class InfoCollectPlanConfirm(BaseModel):
    confirmed: bool = True
    structured: dict[str, Any] | None = None
    supplementary_content: str | None = Field(default=None, max_length=8000)


class PlanConfirm(BaseModel):
    confirmed: bool = True
    supplementary_content: str | None = Field(default=None, max_length=8000)


class MeetingPlanConfirm(PlanConfirm):
    subject: str | None = Field(default=None, max_length=128)
    room: str | None = Field(default=None, max_length=32)
    selected_room: str | None = Field(default=None, max_length=32)
    room_flexible: bool | None = None
    attendees: str | None = Field(default=None, max_length=256)
    date_hint: str | None = Field(default=None, max_length=64)
    start_hint: str | None = Field(default=None, max_length=16)
    end_hint: str | None = Field(default=None, max_length=16)


class SendMessageData(BaseModel):
    user_message: MessagePublic
    assistant_message: MessagePublic
