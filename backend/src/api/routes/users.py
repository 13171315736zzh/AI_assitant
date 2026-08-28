from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from pycore.api import APIRouter

from src.api.deps import get_current_user
from src.api.responses import success
from src.db.session import get_db
from src.models.user import UserPublic
from src.repositories.user import UserRepository
from src.repositories.user_settings import UserSettingsRepository
from src.services.settings import SettingsService

router = APIRouter(prefix="/api/users", tags=["users"])


def _service(db: AsyncSession) -> SettingsService:
    return SettingsService(UserSettingsRepository(db), UserRepository(db))


@router.delete("/me/memory")
async def clear_memory(
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await _service(db).clear_memory(current_user.id)
    return success(result.model_dump())
