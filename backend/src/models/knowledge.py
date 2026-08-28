from pydantic import BaseModel, Field


class DocumentPublic(BaseModel):
    id: str
    filename: str
    file_type: str
    updated_at: str


class AdminDocumentPublic(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    uploaded_by: str
    created_at: str
    progress_percent: int | None = None


class DocumentUploadData(BaseModel):
    id: str
    filename: str
    status: str
    progress: dict


class DocumentProgressData(BaseModel):
    id: str
    status: str
    progress: dict


class DeleteDocumentData(BaseModel):
    deleted: bool


class QAItemPublic(BaseModel):
    id: str
    question: str
    answer: str
    source_clause: str
    document_name: str


class AdminQAItemPublic(BaseModel):
    id: str
    document_id: str
    question: str
    answer: str
    source_clause: str


class KnowledgeSearchData(BaseModel):
    qa_results: list[QAItemPublic]
    document_results: list[DocumentPublic]


class SearchTestRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)


class SearchTestResult(BaseModel):
    type: str
    question: str
    answer: str
    similarity: float
    source_clause: str


class SearchTestData(BaseModel):
    results: list[SearchTestResult]
