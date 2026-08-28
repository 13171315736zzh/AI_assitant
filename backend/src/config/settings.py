from pathlib import Path

from pycore.core import BaseSettings, ConfigManager

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "app.toml"

_manager: ConfigManager | None = None


class AppSettings(BaseSettings):
    debug: bool = False
    secret_key: str = "change-me"
    database_url: str = "sqlite+aiosqlite:///../data/sqlite/app.db"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]
    app_name: str = "ai-assistant"
    app_version: str = "1.0.0"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-max"
    llm_vision_model: str = "qwen-vl-plus"
    llm_temperature: float = 0.7
    llm_timeout_seconds: int = 60
    llm_max_tokens: int = 4096
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"


def get_settings() -> AppSettings:
    global _manager
    if _manager is None:
        _manager = ConfigManager()
        _manager.load(AppSettings, CONFIG_PATH, use_env=True)
    return _manager.settings
