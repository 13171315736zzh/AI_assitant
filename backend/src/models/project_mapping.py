from pydantic import BaseModel, ConfigDict, Field


class ProjectMappingPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_name: str
    aliases: str
    city: str
    district: str
    address: str
    policy_city: str
    remark: str
    updated_by: str
    updated_at: str


class ProjectMappingCreate(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=128)
    aliases: str = Field(default="", max_length=512)
    city: str = Field(default="", max_length=64)
    district: str = Field(default="", max_length=64)
    address: str = Field(default="", max_length=256)
    policy_city: str = Field(default="", max_length=64)
    remark: str = Field(default="", max_length=500)


class ProjectMappingUpdate(BaseModel):
    project_name: str | None = Field(default=None, max_length=128)
    aliases: str | None = Field(default=None, max_length=512)
    city: str | None = Field(default=None, max_length=64)
    district: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=256)
    policy_city: str | None = Field(default=None, max_length=64)
    remark: str | None = Field(default=None, max_length=500)


class ProjectMappingImportResult(BaseModel):
    imported: int
    updated: int
    skipped: int
    errors: list[str]
