from sqlalchemy import Boolean, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models import Base


class UserSettingsRecord(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    theme: Mapped[str] = mapped_column(String(16), default="light")
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    memory_items_json: Mapped[list] = mapped_column(JSON, default=list)
    structured_json: Mapped[dict] = mapped_column(JSON, default=dict)
