import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.types.attempt_types import (
    AttemptStatus,
    ErrorKind,
    WebhookOutcome,
    WebhookStatus,
)
from app.core.types.model_types import Provider
from app.core.types.task_types import TaskStatus
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.task_repository import TaskRepository
from app.services.task.task_transition_service import (
    Event,
    TaskTransitionService,
)

logger = logging.getLogger(__name__)


class TaskResultService:
    """Результат провайдера: одна транзакция на вызов."""

    def __init__(
        self,
        session: AsyncSession,
        transition: TaskTransitionService,
        tasks: TaskRepository,
        attempts: AttemptRepository,
    ) -> None:
        self._session = session
        self._transition = transition
        self._tasks = tasks
        self._attempts = attempts

    async def apply_provider_webhook(
        self,
        provider: Provider,
        attempt_id: UUID,
        external_id: str,
        status: WebhookStatus,
        result_url: str | None,
        error_kind: ErrorKind | None,
    ) -> WebhookOutcome:
        """Применяет completed или failed от провайдера ровно один раз.

        Бизнес-исходов-исключений нет: неизвестная, чужая или закрытая попытка
        даёт IGNORED.
        """
        events: list[Event] = []
        async with self._session.begin():
            outcome = await self._apply_webhook(
                provider,
                attempt_id,
                external_id,
                status,
                result_url,
                error_kind,
                events,
            )

        # логи после выхода из транзакции, включая ветки IGNORED
        for level, message, args in events:
            logger.log(level, message, *args)
        return outcome

    async def _apply_webhook(
        self,
        provider: Provider,
        attempt_id: UUID,
        external_id: str,
        status: WebhookStatus,
        result_url: str | None,
        error_kind: ErrorKind | None,
        events: list[Event],
    ) -> WebhookOutcome:
        """Тело транзакции вебхука; логи только копит в events."""
        locked = await self._transition.lock_for_attempt(attempt_id)
        if locked is None:
            events.append(
                (logging.WARNING, "webhook_unknown attempt_id=%s", (attempt_id,))
            )
            return WebhookOutcome.IGNORED
        if locked.provider != provider:
            events.append(
                (
                    logging.WARNING,
                    "webhook_provider_mismatch attempt_id=%s name=%s provider=%s",
                    (attempt_id, provider, locked.provider),
                )
            )
            return WebhookOutcome.IGNORED
        user, task, attempt = locked.user, locked.task, locked.attempt

        if task.status != TaskStatus.RUNNING:
            events.append(
                (
                    logging.WARNING,
                    "webhook_ignored attempt_id=%s reason=task_finished",
                    (attempt_id,),
                )
            )
            return WebhookOutcome.IGNORED

        if status == WebhookStatus.COMPLETED:
            closed = {AttemptStatus.COMPLETED, AttemptStatus.SUPERSEDED}
        else:
            closed = {
                AttemptStatus.COMPLETED,
                AttemptStatus.FAILED,
                AttemptStatus.SUPERSEDED,
            }
        if attempt.status in closed:
            events.append(
                (
                    logging.WARNING,
                    "webhook_ignored attempt_id=%s reason=attempt_closed",
                    (attempt_id,),
                )
            )
            return WebhookOutcome.IGNORED

        if status == WebhookStatus.COMPLETED:
            # failed-попытка принимается: результат пришёл после отказа
            late = attempt.status == AttemptStatus.FAILED
            await self._attempts.finish(
                self._session, attempt, AttemptStatus.COMPLETED, None, external_id
            )
            await self._attempts.supersede_live(self._session, task.id, attempt.id)
            await self._tasks.finish(
                self._session, task, TaskStatus.COMPLETED, result_url
            )
            events.append(
                (
                    logging.INFO,
                    "task_completed task_id=%s attempt_id=%s",
                    (task.id, attempt.id),
                )
            )
            if late:
                events.append(
                    (
                        logging.WARNING,
                        "late_completed_accepted task_id=%s attempt_id=%s",
                        (task.id, attempt.id),
                    )
                )
            return WebhookOutcome.APPLIED

        # провайдер не прислал вид ошибки: считаем технической
        kind = error_kind or ErrorKind.TECHNICAL
        await self._attempts.finish(
            self._session, attempt, AttemptStatus.FAILED, kind, external_id
        )
        events.append(
            (
                logging.INFO,
                "attempt_failed task_id=%s attempt_id=%s source=webhook error_kind=%s",
                (task.id, attempt.id, kind),
            )
        )
        await self._transition.advance(user, task, attempt, kind, events)
        return WebhookOutcome.APPLIED
