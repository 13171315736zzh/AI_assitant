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


class TaskStatusPublic(BaseModel):
    id: str
    status: str


class TaskConfirmPublic(BaseModel):
    id: str
    status: str
    current_step: int
