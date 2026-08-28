from pydantic import BaseModel, Field


class ConversationUserPublic(BaseModel):
    display_name: str
    employee_id: str


class AdminConversationPublic(BaseModel):
    id: str
    user: ConversationUserPublic
    title: str
    status: str
    message_count: int
    created_at: str
    updated_at: str


class ConversationMessagePreview(BaseModel):
    role: str
    content: str
    created_at: str


class AdminConversationDetailPublic(AdminConversationPublic):
    ended_reason: str | None
    messages: list[ConversationMessagePreview]
    task_summary: str | None


class ConversationStatsPublic(BaseModel):
    total_sessions: int
    active_sessions: int
    today_new_sessions: int


class ConversationExportPublic(BaseModel):
    download_url: str


class SystemConfigPublic(BaseModel):
    system_name: str
    welcome_message: str
    default_model: str
    temperature: float
    session_retention_days: int
    max_concurrent_sessions: int
    log_level: str
    api_timeout_seconds: int


class SystemConfigUpdate(BaseModel):
    system_name: str | None = None
    welcome_message: str | None = None
    default_model: str | None = None
    temperature: float | None = Field(None, ge=0, le=1)
    session_retention_days: int | None = Field(None, ge=1)
    max_concurrent_sessions: int | None = Field(None, ge=1)
    log_level: str | None = None
    api_timeout_seconds: int | None = Field(None, ge=1)
