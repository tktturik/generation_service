from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.payment_model import PaymentModel


class PaymentRepository:
    """Запросы к payments. Не коммитит: транзакцией управляет вызывающий."""

    async def insert_if_absent(
        self, session: AsyncSession, payment_id: str, user_id: int, tokens: int
    ) -> bool:
        """Вставляет платёж; True, если строка вставлена, False при дубле payment_id."""
        stmt = (
            insert(PaymentModel)
            .values(payment_id=payment_id, user_id=user_id, tokens=tokens)
            .on_conflict_do_nothing(index_elements=[PaymentModel.payment_id])
            .returning(PaymentModel.payment_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
