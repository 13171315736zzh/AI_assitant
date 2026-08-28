from pydantic import BaseModel, Field


class TicketCreateRequest(BaseModel):
    session_id: str | None = None
    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=2000)


class TicketPublic(BaseModel):
    id: str
    session_id: str | None
    title: str
    description: str | None = None
    status: str
    created_at: str


class TicketStatusPublic(BaseModel):
    id: str
    status: str
    title: str
    created_at: str
