from pycore.api import APIRouter

from src.api.responses import success
from src.config.settings import get_settings
from src.models.common import ApiResponse, HealthData

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[HealthData])
async def health_check():
    settings = get_settings()
    return success({"status": "ok", "version": settings.app_version})
