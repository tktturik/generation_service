import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config.settings import WorkerSettings
from app.core.types.attempt_types import OverdueAttempt, OverdueKind
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.ledger_entry_repository import LedgerEntryRepository
from app.repositories.model_leg_repository import ModelLegRepository
from app.repositories.model_repository import ModelRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.catalog_service import CatalogService
from app.services.ledger_service import LedgerService
from app.services.task import TaskTransitionService, WatchdogService

logger = logging.getLogger(__name__)

WATCHDOG_BATCH = 50


class WatchdogWorker:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        settings: WorkerSettings,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._settings = settings

    async def run(self) -> None:
        """Бесконечный цикл до отмены; CancelledError не перехватывается."""
        while True:
            try:
                has_more = await self._tick()
            except Exception:  # noqa: BLE001
                # фоновый цикл должен пережить любой сбой тика;
                # CancelledError — BaseException и проходит
                logger.exception("watchdog_tick_failed")
                has_more = False
            if not has_more:
                await asyncio.sleep(self._settings.watchdog_poll_seconds)

    async def _tick(self) -> bool:
        """Возвращает True, если кандидатов одного типа ровно WATCHDOG_BATCH."""
        async with self._sessionmaker() as session:
            candidates = await self._build_service(session).find_overdue(
                self._settings.provider_timeout, WATCHDOG_BATCH
            )
        for candidate in candidates:
            await self._handle_one(candidate)
        return any(
            sum(1 for c in candidates if c.kind is kind) == WATCHDOG_BATCH
            for kind in OverdueKind
        )

    async def _handle_one(self, candidate: OverdueAttempt) -> None:
        try:
            # своя сессия на кандидата: сбой одного не откатывает остальных
            async with self._sessionmaker() as session:
                service = self._build_service(session)
                if candidate.kind is OverdueKind.LEASE_EXPIRED:
                    # для LEASE_EXPIRED find_overdue всегда заполняет lease_until
                    assert candidate.lease_until is not None  # noqa: S101
                    await service.expire_lease(
                        candidate.attempt_id,
                        candidate.lease_until,
                        self._settings.max_lease_expirations,
                    )
                else:
                    await service.time_out(candidate.attempt_id)
        except Exception:  # noqa: BLE001
            # сбой кандидата не должен останавливать остальных
            logger.exception(
                "watchdog_candidate_failed attempt_id=%s kind=%s",
                candidate.attempt_id,
                candidate.kind,
            )

    def _build_service(self, session: AsyncSession) -> WatchdogService:
        ledger = LedgerService(session, UserRepository(), LedgerEntryRepository())
        catalog = CatalogService(session, ModelRepository(), ModelLegRepository())
        attempts = AttemptRepository()
        transition = TaskTransitionService(
            session, ledger, catalog, TaskRepository(), attempts
        )
        return WatchdogService(session, transition, attempts)
