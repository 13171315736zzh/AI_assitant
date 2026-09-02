from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import get_settings
from src.db.models import Base
from src.db.chat_models import MessageRecord, SessionRecord  # noqa: F401
from src.db.form_models import FormRecord  # noqa: F401
from src.db.knowledge_models import DocumentChunkRecord, DocumentRecord, QARecord  # noqa: F401
from src.db.task_models import TaskRecord  # noqa: F401
from src.db.user_model import User  # noqa: F401
from src.db.user_settings_models import UserSettingsRecord  # noqa: F401
from src.db.system_config_models import SystemConfigRecord  # noqa: F401
from src.db.project_mapping_models import ProjectMappingRecord  # noqa: F401

_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return
    # sqlite+aiosqlite:///../data/sqlite/app.db → resolve relative path
    raw = database_url.split("///", 1)[-1]
    db_path = Path(__file__).resolve().parents[2] / raw
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _get_engine():
    global _engine, _async_session_factory
    if _engine is None:
        settings = get_settings()
        _ensure_sqlite_dir(settings.database_url)
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            connect_args={"timeout": 30},
        )
        _async_session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
    return _engine


async def init_db() -> None:
    engine = _get_engine()
    async with engine.begin() as conn:
        if str(engine.url).startswith("sqlite"):
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
        await conn.run_sync(Base.metadata.create_all)
        # SQLite 无自动迁移：tasks 表结构变更时重建
        result = await conn.execute(text("PRAGMA table_info(tasks)"))
        cols = [row[1] for row in result.fetchall()]
        if cols and "user_id" not in cols:
            await conn.execute(text("DROP TABLE tasks"))
            await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    _get_engine()
    assert _async_session_factory is not None
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db():
    async with get_session() as session:
        yield session
