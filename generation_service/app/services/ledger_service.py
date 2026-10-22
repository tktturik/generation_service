from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.types.ledger_entry_types import LedgerEntry, LedgerEntryKind
from app.core.types.user_types import User
from app.database.models.ledger_entry_model import LedgerEntryModel
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.user_repository import UserRepository


class LedgerService:
    """Баланс и журнал. Транзакций не открывает:
    вызывается только внутри транзакции вызывающего."""

    def __init__(
        self,
        session: AsyncSession,
        users: UserRepository,
        entries: LedgerEntryRepository,
    ) -> None:
        self._session = session
        self._users = users
        self._entries = entries

    async def lock_user(self, user_id: int) -> User:
        """Блокирует пользователя FOR UPDATE; нет пользователя: NotFoundError."""
        model = await self._users.get_for_update(self._session, user_id)
        if model is None:
            raise NotFoundError("USER_NOT_FOUND", f"User {user_id} not found")
        return User(id=model.id, balance=model.balance)

    async def credit_payment(
        self, user: User, payment_id: str, tokens: int
    ) -> LedgerEntry:
        """Начисляет токены за оплату; user должен быть получен из lock_user."""
        return await self._apply(
            user,
            kind=LedgerEntryKind.PAYMENT,
            delta=tokens,
            payment_id=payment_id,
        )

    async def _apply(
        self,
        user: User,
        kind: LedgerEntryKind,
        delta: int,
        task_id: UUID | None = None,
        payment_id: str | None = None,
    ) -> LedgerEntry:
        # balance_after берём из RETURNING:
        # ORM-объект пользователя может быть устаревшим
        balance_after = await self._users.add_balance(self._session, user.id, delta)
        model = await self._entries.add(
            self._session,
            user_id=user.id,
            kind=kind,
            amount=delta,
            balance_after=balance_after,
            task_id=task_id,
            payment_id=payment_id,
        )
        return _to_entry(model)


def _to_entry(model: LedgerEntryModel) -> LedgerEntry:
    return LedgerEntry(
        kind=LedgerEntryKind(model.kind),
        amount=model.amount,
        balance_after=model.balance_after,
        task_id=model.task_id,
        payment_id=model.payment_id,
        created_at=model.created_at,
    )
