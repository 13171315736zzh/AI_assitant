from typing import Literal

from pydantic import BaseModel, Field, field_validator

ThemeValue = Literal["light", "dark", "system"]


class MemoryItem(BaseModel):
    key: str = Field(..., min_length=1, max_length=64)
    value: str = Field(..., max_length=512)


class MemoryStructured(BaseModel):
    display_name: str = ""
    gender: str = "unknown"
    id_number: str = ""
    employee_id: str = ""
    job_role: str = ""
    position: str = ""
    base_location: str = ""
    department: str = ""
    email: str = ""
    travel_mode_preference: str = ""
    related_projects: list[str] = Field(default_factory=list)

    @field_validator("travel_mode_preference")
    @classmethod
    def validate_travel_mode_preference(cls, value: str) -> str:
        from src.agent.user_memory import normalize_travel_mode_preference

        if not (value or "").strip():
            return ""
        normalized = normalize_travel_mode_preference(value)
        return normalized or ""

    @field_validator("id_number")
    @classmethod
    def validate_id_number_field(cls, value: str) -> str:
        from src.agent.memory_validators import (
            format_field_error,
            normalize_id_number,
            validate_id_number,
        )

        normalized = normalize_id_number(value)
        if not normalized:
            return ""
        error = validate_id_number(normalized)
        if error:
            raise ValueError(format_field_error("id_number", error))
        return normalized

    @field_validator("employee_id")
    @classmethod
    def validate_employee_id_field(cls, value: str) -> str:
        from src.agent.memory_validators import (
            format_field_error,
            normalize_employee_id,
            validate_employee_id,
        )

        normalized = normalize_employee_id(value)
        if not normalized:
            return ""
        error = validate_employee_id(normalized)
        if error:
            raise ValueError(format_field_error("employee_id", error))
        return normalized


class MemoryPublic(BaseModel):
    memory_enabled: bool
    structured: MemoryStructured
    memory_items: list[MemoryItem]
    field_count: int = 0


class MemoryUpdateRequest(BaseModel):
    memory_enabled: bool | None = None
    structured: MemoryStructured | None = None
    memory_items: list[MemoryItem] | None = None


class ProfilePublic(BaseModel):
    username: str
    display_name: str
    role: str
    employee_id: str


class ThemeUpdateRequest(BaseModel):
    theme: ThemeValue


class ThemePublic(BaseModel):
    theme: ThemeValue


class ChangelogEntry(BaseModel):
    version: str
    date: str
    items: list[str]


class VersionPublic(BaseModel):
    version: str
    release_date: str
    has_update: bool
    changelog: list[ChangelogEntry]


class VersionCheckPublic(BaseModel):
    has_update: bool
    message: str


class ClearMemoryPublic(BaseModel):
    cleared: bool


class WelcomePublic(BaseModel):
    welcome_message: str
