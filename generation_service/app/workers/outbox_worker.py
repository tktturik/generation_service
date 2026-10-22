import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.provider_client import ProviderClient
from app.core.config.settings import WorkerSettings
from app.core.types.attempt_types import ClaimedAttempt
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.model_leg_repository import ModelLegRepository
from app.repositories.model_repository import ModelRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.catalog_service import CatalogService
from app.services.ledger_service import LedgerService
from app.services.outbox_service import OutboxService
from app.services.task import TaskTransitionService, WatchdogService

logger = logging.getLogger(__name__)


class OutboxWorker:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        client: ProviderClient,
        settings: WorkerSettings,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._client = client
        self._settings = settings

    async def run(self) -> None:
        """Бесконечный цикл до отмены; CancelledError не перехватывается."""
        while True:
            try:
                batch_size = await self._tick()
            except Exception:  # noqa: BLE001
                # фоновый цикл должен пережить любой сбой тика;
                # CancelledError — BaseException и проходит
                logger.exception("outbox_tick_failed")
                batch_size = 0
            # полная пачка: вероятно, есть ещё записи, следующий тик сразу
            if batch_size < self._settings.outbox_batch:
                await asyncio.sleep(self._settings.outbox_poll_seconds)

    async def _tick(self) -> int:
        async with self._sessionmaker() as session:
            claimed = await self._build_service(session).claim_batch(
                self._settings.outbox_batch, self._settings.lease_seconds
            )
        if not claimed:
            return 0
        results = await asyncio.gather(
            *(self._dispatch_one(item) for item in claimed),
            return_exceptions=True,
        )
        for item, result in zip(claimed, results, strict=True):
            if isinstance(result, BaseException):
                logger.error(
                    "attempt_dispatch_failed attempt_id=%s task_id=%s",
                    item.attempt_id,
                    item.task_id,
                    exc_info=result,
                )
        return len(claimed)

    async def _dispatch_one(self, claimed: ClaimedAttempt) -> None:
        # своя сессия на попытку: сессия не потокобезопасна для параллельных задач
        async with self._sessionmaker() as session:
            await self._build_service(session).dispatch(claimed)

    def _build_service(self, session: AsyncSession) -> OutboxService:
        attempts = AttemptRepository()
        ledger = LedgerService(session, UserRepository(), LedgerEntryRepository())
        catalog = CatalogService(session, ModelRepository(), ModelLegRepository())
        transition = TaskTransitionService(
            session, ledger, catalog, TaskRepository(), attempts
        )
        watchdog = WatchdogService(session, transition, attempts)
        return OutboxService(session, attempts, self._client, watchdog)
