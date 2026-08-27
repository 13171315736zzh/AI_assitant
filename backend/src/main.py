from pycore.api import APIConfig, APIServer
from pycore.core import Logger, LoggerConfig, LogLevel, get_logger
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.routes.auth import router as auth_router
from src.api.routes.health import router as health_router
from src.api.routes.sessions import router as sessions_router
from src.config.settings import get_settings
from src.db.seed import seed_demo_sessions, seed_users
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


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "请求失败"
    return JSONResponse(
        status_code=exc.status_code,
        content=error(detail, code=exc.status_code),
    )


logger.info("Application configured", host=settings.host, port=settings.port)
