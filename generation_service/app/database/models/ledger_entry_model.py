from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base_model import Base


class LedgerEntryModel(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('payment', 'charge', 'refund')", name="kind_known"),
        # charge списывает (< 0), payment и refund начисляют (> 0)
        CheckConstraint(
            "(kind = 'charge' AND amount < 0) "
            "OR (kind IN ('payment', 'refund') AND amount > 0)",
            name="amount_sign_by_kind",
        ),
        CheckConstraint("balance_after >= 0", name="balance_after_non_negative"),
        Index(
            "uq_ledger_entries_task_id_kind",
            "task_id",
            "kind",
            unique=True,
            postgresql_where="kind IN ('charge', 'refund')",
        ),
        Index(
            "uq_ledger_entries_payment_id",
            "payment_id",
            unique=True,
            postgresql_where="kind = 'payment'",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"))
    payment_id: Mapped[str | None] = mapped_column(ForeignKey("payments.payment_id"))
    kind: Mapped[str] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
