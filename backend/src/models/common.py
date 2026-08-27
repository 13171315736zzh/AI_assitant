from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: T | None = None


class HealthData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(..., examples=["ok"])
    version: str = Field(..., examples=["1.0.0"])


def success(data: Any = None, message: str = "success", code: int = 200) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data}


def error(message: str, code: int = 400) -> dict[str, Any]:
    return {"code": code, "message": message, "data": None}


def paginated(
    items: Any,
    total: int,
    page: int,
    page_size: int,
    message: str = "success",
) -> dict[str, Any]:
    return {
        "code": 200,
        "message": message,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }
