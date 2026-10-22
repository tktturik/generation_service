from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.types.ledger_entry_types import LedgerEntryKind


class LedgerEntryResponse(BaseModel):
    kind: LedgerEntryKind
    amount: int
    balance_after: int
    task_id: UUID | None
    payment_id: str | None
    created_at: datetime


class UserBalanceResponse(BaseModel):
    user_id: int
    balance: int
    entries: list[LedgerEntryResponse]
