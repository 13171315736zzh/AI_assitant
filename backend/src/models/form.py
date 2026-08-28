from pydantic import BaseModel, Field

FORM_TYPES = frozenset({"email", "meeting", "travel", "workpackage"})


class FormPublic(BaseModel):
    form_id: str
    form_type: str
    status: str
    title: str
    fields: dict[str, str]


class FormPreviewRequest(BaseModel):
    session_id: str
    task_id: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)


class FormSubmitRequest(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict)


class FormStatusPublic(BaseModel):
    form_id: str
    status: str


class FormSubmitPublic(BaseModel):
    form_id: str
    status: str
    receipt_id: str
    message: str


class FormReceiptPublic(BaseModel):
    receipt_id: str
    status: str
    summary: str
    submitted_at: str
