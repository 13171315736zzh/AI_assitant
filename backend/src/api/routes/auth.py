from fastapi import Depends
from fastapi.responses import JSONResponse
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.api.responses import error, success
from src.db.session import get_db
from src.models.common import ApiResponse
from src.models.user import LoginData, LoginRequest, UserPublic
from src.repositories.user import UserRepository
from src.services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[LoginData])
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(UserRepository(db))
    result = await auth_service.login(body.username, body.password)
    if result is None:
        return JSONResponse(
            status_code=401,
            content=error("用户名或密码错误", code=401),
        )
    return success(result.model_dump())


@router.post("/logout", response_model=ApiResponse[None])
async def logout(_: UserPublic = Depends(get_current_user)):
    return success(None)


@router.get("/me", response_model=ApiResponse[UserPublic])
async def me(current_user: UserPublic = Depends(get_current_user)):
    return success(current_user.model_dump())
