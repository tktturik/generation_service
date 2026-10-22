from dataclasses import dataclass

from app.core.types.ledger_entry_types import LedgerEntry


@dataclass(frozen=True, slots=True)
class User:
    id: int
    balance: int


@dataclass(frozen=True, slots=True)
class UserBalance:
    user_id: int
    balance: int
    entries: tuple[LedgerEntry, ...]
