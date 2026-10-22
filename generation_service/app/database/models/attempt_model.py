from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base_model import Base


class AttemptModel(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        UniqueConstraint("task_id", "seq"),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent',"
            " 'completed', 'failed', 'superseded')",
            name="status_known",
        ),
        CheckConstraint(
            "error_kind IN ('technical', 'moderation', 'payload')",
            name="error_kind_known",
        ),
        # не более одной живой попытки на задачу
        Index(
            "uq_attempts_task_id_live",
            "task_id",
            unique=True,
            postgresql_where="status IN ('pending', 'sending', 'sent')",
        ),
        Index(
            "ix_attempts_created_at_pending",
            "created_at",
            postgresql_where="status = 'pending'",
        ),
        Index(
            "ix_attempts_lease_until_sending",
            "lease_until",
            postgresql_where="status = 'sending'",
        ),
        Index(
            "ix_attempts_sent_at_sent", "sent_at", postgresql_where="status = 'sent'"
        ),
    )

    # id это attempt_id, генерирует приложение (uuid4)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"))
    leg_id: Mapped[int] = mapped_column(ForeignKey("model_legs.id"))
    seq: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    error_kind: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expirations: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
