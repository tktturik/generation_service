import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import InvalidSignatureError
from app.core.signature import verify_signature
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.model_leg_repository import ModelLegRepository
from app.repositories.model_repository import ModelRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.catalog_service import CatalogService
from app.services.ledger_service import LedgerService
from app.services.payment_service import PaymentService
from app.services.task import TaskResultService, TaskService, TaskTransitionService
from app.services.user_service import UserService

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


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserService:
    return UserService(session, UserRepository(), LedgerEntryRepository())


def get_catalog_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CatalogService:
    return CatalogService(session, ModelRepository(), ModelLegRepository())


def get_task_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    ledger: Annotated[LedgerService, Depends(get_ledger_service)],
    catalog: Annotated[CatalogService, Depends(get_catalog_service)],
) -> TaskService:
    return TaskService(session, ledger, catalog, TaskRepository(), AttemptRepository())


def get_task_transition_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    ledger: Annotated[LedgerService, Depends(get_ledger_service)],
    catalog: Annotated[CatalogService, Depends(get_catalog_service)],
) -> TaskTransitionService:
    return TaskTransitionService(
        session, ledger, catalog, TaskRepository(), AttemptRepository()
    )


def get_task_result_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    transition: Annotated[TaskTransitionService, Depends(get_task_transition_service)],
) -> TaskResultService:
    return TaskResultService(session, transition, TaskRepository(), AttemptRepository())


async def _read_verified_body(request: Request, secret: str) -> bytes:
    body = await request.body()
    if not verify_signature(
        secret,
        body,
        request.headers.get("X-Signature"),
    ):
        logger.warning("signature_invalid path=%s", request.url.path)
        raise InvalidSignatureError()
    return body


async def verify_payment_signature(request: Request) -> bytes:
    """Читает сырое тело и проверяет подпись до разбора JSON.

    Ошибка: InvalidSignatureError.
    """
    return await _read_verified_body(request, settings.security.payment_webhook_secret)


async def verify_provider_signature(request: Request) -> bytes:
    """Как verify_payment_signature, но с секретом вебхуков провайдеров.

    Ошибка: InvalidSignatureError.
    """
    return await _read_verified_body(request, settings.security.provider_webhook_secret)
