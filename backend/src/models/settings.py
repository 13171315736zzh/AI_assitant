from typing import Literal

from pydantic import BaseModel, Field

ThemeValue = Literal["light", "dark", "system"]


class MemoryItem(BaseModel):
    key: str = Field(..., min_length=1, max_length=64)
    value: str = Field(..., max_length=512)


class MemoryStructured(BaseModel):
    employee_id: str = ""
    department: str = ""
    position: str = ""
    email: str = ""
    travel_mode_preference: str = ""
    related_projects: list[str] = Field(default_factory=list)
    gender: str = "unknown"


class MemoryPublic(BaseModel):
    memory_enabled: bool
    structured: MemoryStructured
    memory_items: list[MemoryItem]


class MemoryUpdateRequest(BaseModel):
    memory_enabled: bool | None = None
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
