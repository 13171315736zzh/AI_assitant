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


class WorkpackageConfirm(BaseModel):
    confirmed: bool = True
    entries: list[dict[str, Any]] | None = None


class PlanConfirm(BaseModel):
    confirmed: bool = True


class SendMessageData(BaseModel):
    user_message: MessagePublic
    assistant_message: MessagePublic
