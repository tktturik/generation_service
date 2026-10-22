from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.ledger_entry_model import LedgerEntryModel


class LedgerEntryRepository:
    """Запросы к ledger_entries. Не коммитит: транзакцией управляет вызывающий."""

    async def add(
        self,
        session: AsyncSession,
        user_id: int,
        kind: str,
        amount: int,
        balance_after: int,
        task_id: UUID | None = None,
        payment_id: str | None = None,
    ) -> LedgerEntryModel:
        entry = LedgerEntryModel(
            user_id=user_id,
            kind=kind,
            amount=amount,
            balance_after=balance_after,
            task_id=task_id,
            payment_id=payment_id,
        )
        session.add(entry)
        await session.flush()
        await session.refresh(entry, attribute_names=["created_at"])
        return entry

    async def list_recent(
        self, session: AsyncSession, user_id: int, limit: int
    ) -> list[LedgerEntryModel]:
        stmt = (
            select(LedgerEntryModel)
            .where(LedgerEntryModel.user_id == user_id)
            .order_by(LedgerEntryModel.created_at.desc(), LedgerEntryModel.id.desc())
            .limit(limit)
        )
        return list((await session.scalars(stmt)).all())
