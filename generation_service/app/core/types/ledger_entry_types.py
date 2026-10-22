from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class LedgerEntryKind(StrEnum):
    PAYMENT = "payment"
    CHARGE = "charge"
    REFUND = "refund"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    kind: LedgerEntryKind
    amount: int
    balance_after: int
    task_id: UUID | None
    payment_id: str | None
    created_at: datetime
