from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.api.responses import success
from src.db.session import get_db
from src.models.settings import MemoryUpdateRequest, ThemeUpdateRequest
from src.models.user import UserPublic
from src.repositories.system_config import SystemConfigRepository
from src.repositories.user import UserRepository
from src.repositories.user_settings import UserSettingsRepository
from src.services.settings import SettingsService
from pycore.api import APIRouter

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _service(db: AsyncSession) -> SettingsService:
    return SettingsService(
        UserSettingsRepository(db),
        UserRepository(db),
        SystemConfigRepository(db),
    )


@router.get("/profile")
async def get_profile(
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _service(db).get_profile(current_user.id)
    return success(profile.model_dump())


@router.get("/welcome")
async def get_welcome(
    _: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    welcome = await _service(db).get_welcome()
    return success(welcome.model_dump())


@router.get("/theme")
async def get_theme(
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    theme = await _service(db).get_theme(current_user.id)
    return success(theme.model_dump())


@router.patch("/theme")
async def update_theme(
    body: ThemeUpdateRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    theme = await _service(db).update_theme(current_user.id, body)
    return success(theme.model_dump())


@router.get("/version")
async def get_version(
    _: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    version = await _service(db).get_version()
    return success(version.model_dump())


@router.post("/version/check")
async def check_version(
    _: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await _service(db).check_version()
    return success(result.model_dump())


@router.get("/memory")
async def get_memory(
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    memory = await _service(db).get_memory(current_user.id)
    return success(memory.model_dump())


@router.patch("/memory")
async def update_memory(
    body: MemoryUpdateRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    memory = await _service(db).update_memory(current_user.id, body)
    return success(memory.model_dump())
