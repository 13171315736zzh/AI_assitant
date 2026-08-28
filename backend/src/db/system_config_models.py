from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models import Base


class SystemConfigRecord(Base):
    __tablename__ = "system_config"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default="default")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
