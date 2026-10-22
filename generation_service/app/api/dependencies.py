import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import InvalidSignatureError
from app.core.signature import verify_signature
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.user_repository import UserRepository
from app.services.ledger_service import LedgerService
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    # коммит не здесь: транзакцией управляет сервис
    async with request.app.state.sessionmaker() as session:
        yield session


def get_ledger_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LedgerService:
    return LedgerService(session, UserRepository(), LedgerEntryRepository())


def get_payment_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    ledger: Annotated[LedgerService, Depends(get_ledger_service)],
) -> PaymentService:
    return PaymentService(session, ledger, PaymentRepository())


async def verify_payment_signature(request: Request) -> bytes:
    """Читает сырое тело и проверяет подпись до разбора JSON.

    Ошибка: InvalidSignatureError.
    """
    body = await request.body()
    if not verify_signature(
        settings.security.payment_webhook_secret,
        body,
        request.headers.get("X-Signature"),
    ):
        logger.warning("signature_invalid path=%s", request.url.path)
        raise InvalidSignatureError()
    return body
