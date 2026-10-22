import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.types.attempt_types import (
    AttemptStatus,
    ErrorKind,
    OverdueAttempt,
    OverdueKind,
)
from app.core.types.task_types import TaskStatus
from app.database.models.attempt_model import AttemptModel
from app.database.models.task_model import TaskModel
from app.repositories.attempt_repository import AttemptRepository
from app.services.task.task_transition_service import Event, TaskTransitionService

logger = logging.getLogger(__name__)


class WatchdogService:
    """Сторож и отказ отправки: одна транзакция на вызов."""

    def __init__(
        self,
        session: AsyncSession,
        transition: TaskTransitionService,
        attempts: AttemptRepository,
    ) -> None:
        self._session = session
        self._transition = transition
        self._attempts = attempts

    async def fail_on_send(self, attempt_id: UUID, lease_until: datetime) -> None:
        """Закрывает попытку как technical после отказа или таймаута отправки.

        Устаревшая аренда или чужое состояние попытки: выход без изменений.
        """
        events: list[Event] = []
        async with self._session.begin():
            locked = await self._transition.lock_for_attempt(attempt_id)
            if (
                locked is None
                or locked.attempt.status != AttemptStatus.SENDING
                or locked.attempt.lease_until != lease_until
            ):
                # изменений нет, лог до выхода безопасен
                logger.debug("attempt_send_stale attempt_id=%s", attempt_id)
                return
            user, task, attempt = locked.user, locked.task, locked.attempt

            await self._attempts.finish(
                self._session, attempt, AttemptStatus.FAILED, ErrorKind.TECHNICAL, None
            )
            events.append(
                (
                    logging.INFO,
                    "attempt_failed task_id=%s attempt_id=%s source=send error_kind=%s",
                    (task.id, attempt.id, ErrorKind.TECHNICAL),
                )
            )
            if task.status == TaskStatus.RUNNING:
                await self._transition.advance(
                    user, task, attempt, ErrorKind.TECHNICAL, events
                )

        # логи после выхода из транзакции: при откате ничего не пишем
        for level, message, args in events:
            logger.log(level, message, *args)

    async def find_overdue(
        self, provider_timeout: int, limit: int
    ) -> list[OverdueAttempt]:
        """Просроченные попытки без блокировок: сначала аренды, затем таймауты."""
        async with self._session.begin():
            expired = await self._attempts.find_expired_leases(self._session, limit)
            timed_out = await self._attempts.find_timed_out(
                self._session, provider_timeout, limit
            )
        return [
            OverdueAttempt(attempt_id, OverdueKind.LEASE_EXPIRED, lease_until)
            for attempt_id, lease_until in expired
        ] + [
            OverdueAttempt(attempt_id, OverdueKind.PROVIDER_TIMEOUT, None)
            for attempt_id in timed_out
        ]

    async def expire_lease(
        self, attempt_id: UUID, lease_until: datetime, max_lease_expirations: int
    ) -> None:
        """Обрабатывает истёкшую аренду: возврат в pending или technical-отказ.

        Устаревшая аренда или чужое состояние попытки: выход без изменений.
        """
        events: list[Event] = []
        async with self._session.begin():
            locked = await self._transition.lock_for_attempt(attempt_id)
            if (
                locked is None
                or locked.attempt.status != AttemptStatus.SENDING
                or locked.attempt.lease_until != lease_until
            ):
                # изменений нет, лог до выхода безопасен
                logger.debug("watchdog_stale attempt_id=%s", attempt_id)
                return
            user, task, attempt = locked.user, locked.task, locked.attempt

            if task.status != TaskStatus.RUNNING:
                # по инварианту невозможно: закрываем попытку без продвижения
                await self._finish_by_watchdog(attempt, task, events)
            else:
                expiration = attempt.lease_expirations + 1
                events.append(
                    (
                        logging.WARNING,
                        "attempt_lease_expired attempt_id=%s task_id=%s"
                        " lease_expirations=%s",
                        (attempt.id, task.id, expiration),
                    )
                )
                if expiration < max_lease_expirations:
                    await self._attempts.release_lease(self._session, attempt)
                else:
                    await self._finish_by_watchdog(attempt, task, events)
                    await self._transition.advance(
                        user, task, attempt, ErrorKind.TECHNICAL, events
                    )

        # логи после выхода из транзакции: при откате ничего не пишем
        for level, message, args in events:
            logger.log(level, message, *args)

    async def time_out(self, attempt_id: UUID) -> None:
        """Закрывает sent-попытку без ответа провайдера как technical.

        Чужое состояние попытки: выход без изменений.
        """
        events: list[Event] = []
        async with self._session.begin():
            locked = await self._transition.lock_for_attempt(attempt_id)
            # sent_at ставится один раз, поэтому второй маркер не нужен
            if locked is None or locked.attempt.status != AttemptStatus.SENT:
                logger.debug("watchdog_stale attempt_id=%s", attempt_id)
                return
            user, task, attempt = locked.user, locked.task, locked.attempt

            events.append(
                (
                    logging.WARNING,
                    "attempt_timed_out attempt_id=%s task_id=%s provider=%s",
                    (attempt.id, task.id, locked.provider),
                )
            )
            await self._finish_by_watchdog(attempt, task, events)
            if task.status == TaskStatus.RUNNING:
                await self._transition.advance(
                    user, task, attempt, ErrorKind.TECHNICAL, events
                )

        # логи после выхода из транзакции: при откате ничего не пишем
        for level, message, args in events:
            logger.log(level, message, *args)

    async def _finish_by_watchdog(
        self, attempt: AttemptModel, task: TaskModel, events: list[Event]
    ) -> None:
        """Закрывает попытку как failed/technical по решению сторожа."""
        await self._attempts.finish(
            self._session, attempt, AttemptStatus.FAILED, ErrorKind.TECHNICAL, None
        )
        events.append(
            (
                logging.INFO,
                "attempt_failed task_id=%s attempt_id=%s source=watchdog error_kind=%s",
                (task.id, attempt.id, ErrorKind.TECHNICAL),
            )
        )
