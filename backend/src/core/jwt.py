from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError

from src.config.settings import AppSettings, get_settings


def create_access_token(user_id: int, settings: AppSettings | None = None) -> str:
    cfg = settings or get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=cfg.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, cfg.secret_key, algorithm=cfg.jwt_algorithm)


def decode_user_id(token: str, settings: AppSettings | None = None) -> int | None:
    cfg = settings or get_settings()
    try:
        payload = jwt.decode(token, cfg.secret_key, algorithms=[cfg.jwt_algorithm])
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except (InvalidTokenError, ValueError):
        return None
