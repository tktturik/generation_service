from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base_model import Base


class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')", name="status_known"
        ),
        Index(
            "ix_tasks_user_id_running", "user_id", postgresql_where="status = 'running'"
        ),
    )

    # id генерирует приложение (uuid4), серверного значения нет
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    model_slug: Mapped[str] = mapped_column(ForeignKey("models.slug"))
    prompt: Mapped[str] = mapped_column(Text)
    ref_images: Mapped[list[str]] = mapped_column(JSONB)
    price_charged: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text)
    result_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
