from pycore.api import APIConfig, APIServer
from pycore.core import Logger, LoggerConfig, LogLevel, get_logger
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.routes.admin import router as admin_router
from src.api.routes.auth import router as auth_router
from src.api.routes.health import router as health_router
from src.api.routes.forms import router as forms_router
from src.api.routes.knowledge import admin_router as admin_knowledge_router
from src.api.routes.knowledge import router as knowledge_router
from src.api.routes.settings import router as settings_router
from src.api.routes.sessions import router as sessions_router
from src.api.routes.tasks import router as tasks_router
from src.api.routes.tickets import router as tickets_router
from src.api.routes.project_mapping import router as project_mapping_router
from src.api.routes.users import router as users_router
from src.config.settings import get_settings
from src.integrations.llm_factory import verify_llm_connection
from src.db.seed import (
    seed_demo_forms,
    seed_demo_sessions,
    seed_demo_tasks,
    seed_knowledge,
    seed_project_mappings,
    seed_user_settings,
    seed_users,
)
from src.db.session import close_db, init_db
from src.models.common import error

settings = get_settings()

Logger.configure(
    LoggerConfig(
        level=LogLevel.DEBUG if settings.debug else LogLevel.INFO,
        app_name=settings.app_name,
        json_format=False,
    )
)
logger = get_logger()


async def startup() -> None:
    await init_db()
    await seed_users()
    await seed_demo_sessions()
    await seed_demo_tasks()
    await seed_demo_forms()
    await seed_user_settings()
    await seed_knowledge()
    await seed_project_mappings()
    if await verify_llm_connection():
        logger.info("LLM connectivity check passed")
    else:
        logger.warning("LLM connectivity check failed; chat replies may be unavailable")


server = APIServer(
    APIConfig(
        title="智能办公助手 Agent API",
        version=settings.app_version,
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        cors_origins=settings.cors_origins,
    )
)

server.on_startup(startup)
server.on_shutdown(close_db)

app = server.app
app.router.routes[:] = [
    route for route in app.router.routes if getattr(route, "path", None) != "/health"
]
app.include_router(health_router.router)
app.include_router(auth_router.router)
app.include_router(sessions_router.router)
app.include_router(tasks_router.router)
app.include_router(forms_router.router)
app.include_router(knowledge_router.router)
app.include_router(admin_knowledge_router.router)
app.include_router(settings_router.router)
app.include_router(users_router.router)
app.include_router(tickets_router.router)
app.include_router(admin_router.router)
app.include_router(project_mapping_router.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "请求失败"
    return JSONResponse(
        status_code=exc.status_code,
        content=error(detail, code=exc.status_code),
    )


logger.info("Application configured", host=settings.host, port=settings.port)
