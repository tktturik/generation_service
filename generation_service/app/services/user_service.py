from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.types.ledger_entry_types import LedgerEntry, LedgerEntryKind
from app.core.types.user_types import UserBalance
from app.database.models.ledger_entry_model import LedgerEntryModel
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.user_repository import UserRepository

# Сколько последних строк журнала отдаёт чтение баланса (D30)
RECENT_ENTRIES_LIMIT = 20


def _to_entry(model: LedgerEntryModel) -> LedgerEntry:
    return LedgerEntry(
        kind=LedgerEntryKind(model.kind),
        amount=model.amount,
        balance_after=model.balance_after,
        task_id=model.task_id,
        payment_id=model.payment_id,
        created_at=model.created_at,
    )


class UserService:
    def __init__(
        self,
        session: AsyncSession,
        users: UserRepository,
        entries: LedgerEntryRepository,
    ) -> None:
        self.session = session
        self.users = users
        self.entries = entries

    async def get_balance(self, user_id: int) -> UserBalance:
        async with self.session.begin():
            # FOR SHARE ждёт денежную транзакцию
            # (FOR UPDATE), поэтому баланс совпадает с журналом
            user = await self.users.get_for_share(self.session, user_id)
            if user is None:
                raise NotFoundError("USER_NOT_FOUND", "User not found")
            entries = await self.entries.list_recent(
                self.session, user_id, RECENT_ENTRIES_LIMIT
            )
        return UserBalance(
            user_id=user.id,
            balance=user.balance,
            entries=tuple(_to_entry(entry) for entry in entries),
        )
