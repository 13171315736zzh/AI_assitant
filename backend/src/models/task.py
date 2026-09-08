from pydantic import BaseModel, ConfigDict, Field


class TaskStepPublic(BaseModel):
    step_id: int
    action: str
    tool: str
    status: str
    depends_on: list[int] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)
    result: dict | None = None


class TaskPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    goal: str
    status: str
    current_step: int
    total_steps: int
    replan_count: int
    steps: list[TaskStepPublic]
    created_at: str


class TaskConfirmRequest(BaseModel):
    step_id: int
    params: dict = Field(default_factory=dict)


class TaskStepUpdateRequest(BaseModel):
    params: dict = Field(default_factory=dict)


class EmailSentRequest(BaseModel):
    recipient: str | None = None
    subject: str | None = None
    message_id: str | None = None
    body: str | None = None
    sent_at: str | None = None


class TaskStatusPublic(BaseModel):
    id: str
    status: str


class TaskConfirmPublic(BaseModel):
    id: str
    status: str
    current_step: int


class OaTaskActionPublic(BaseModel):
    task: TaskPublic
    session_id: str
    receipt_id: str | None = None
    assistant_message: dict | None = None


class TaskSummaryPublic(BaseModel):
    id: str
    session_id: str
    goal: str
    status: str
    raw_status: str
    category: str
    category_label: str
    tags: list[str] = Field(default_factory=list)
    completed_steps: int
    total_steps: int
    progress_percent: int
    current_step: int
    replan_count: int
    created_at: str
