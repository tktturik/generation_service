import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.types.payment_types import PaymentOutcome
from app.repositories.payment_repository import PaymentRepository
from app.services.ledger_service import LedgerService

logger = logging.getLogger(__name__)

_SUCCEEDED = "succeeded"


class PaymentService:
    """Обработка оплаты: одна транзакция на вызов."""

    def __init__(
        self,
        session: AsyncSession,
        ledger: LedgerService,
        payments: PaymentRepository,
    ) -> None:
        self._session = session
        self._ledger = ledger
        self._payments = payments

    async def process_payment(
        self, payment_id: str, user_id: int, tokens: int, status: str
    ) -> PaymentOutcome:
        """Начисляет токены один раз на payment_id.

        Ошибки: NotFoundError("USER_NOT_FOUND"). Статус не succeeded БД не трогает.
        """
        if status != _SUCCEEDED:
            logger.info("payment_ignored payment_id=%s status=%s", payment_id, status)
            return PaymentOutcome.IGNORED

        async with self._session.begin():
            user = await self._ledger.lock_user(user_id)
            inserted = await self._payments.insert_if_absent(
                self._session, payment_id, user_id, tokens
            )
            entry = (
                await self._ledger.credit_payment(user, payment_id, tokens)
                if inserted
                else None
            )

        # лог после выхода из транзакции: при откате ничего не пишем
        if entry is None:
            logger.warning(
                "payment_duplicate user_id=%s payment_id=%s tokens=%s",
                user_id,
                payment_id,
                tokens,
            )
            return PaymentOutcome.DUPLICATE
        logger.info(
            "payment_credited user_id=%s payment_id=%s tokens=%s balance_after=%s",
            user_id,
            payment_id,
            tokens,
            entry.balance_after,
        )
        return PaymentOutcome.CREDITED
