from pycore.core import get_logger

from src.core.jwt import create_access_token
from src.core.security import hash_password, verify_password
from src.models.user import LoginData, UserPublic
from src.repositories.user import UserRepository

logger = get_logger()


class AuthService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def login(self, username: str, password: str) -> LoginData | None:
        user = await self.repo.get_by_username(username)
        if user is None or not verify_password(password, user.hashed_password):
            return None
        token = create_access_token(user.id)
        logger.info("User logged in", user_id=user.id, username=user.username)
        return LoginData(
            access_token=token,
            token_type="bearer",
            user=UserPublic.model_validate(user),
        )

    async def get_current_user(self, user_id: int) -> UserPublic | None:
        user = await self.repo.get_by_id(user_id)
        if user is None:
            return None
        return UserPublic.model_validate(user)
