import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.types.attempt_types import ErrorKind
from app.core.types.task_types import TaskStatus
from app.core.types.user_types import User
from app.database.models.attempt_model import AttemptModel
from app.database.models.task_model import TaskModel
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.task_repository import TaskRepository
from app.services.catalog_service import CatalogService, pick_next_leg
from app.services.ledger_service import LedgerService

logger = logging.getLogger(__name__)

# отложенное событие лога: (уровень, шаблон, аргументы); пишется после коммита
Event = tuple[int, str, tuple[object, ...]]


@dataclass(frozen=True, slots=True)
class LockedAttempt:
    """Заблокированные пользователь, задача и попытка; provider из маршрута."""

    user: User
    task: TaskModel
    attempt: AttemptModel
    provider: str


class TaskTransitionService:
    """Переходы задачи: блокировки и продвижение по ногам.

    Своих транзакций нет: вызывается только внутри транзакции вызывающего.
    """

    def __init__(
        self,
        session: AsyncSession,
        ledger: LedgerService,
        catalog: CatalogService,
        tasks: TaskRepository,
        attempts: AttemptRepository,
    ) -> None:
        self._session = session
        self._ledger = ledger
        self._catalog = catalog
        self._tasks = tasks
        self._attempts = attempts

    async def lock_for_attempt(self, attempt_id: UUID) -> LockedAttempt | None:
        """Блокирует пользователь -> задача -> попытка; статусы не проверяет.

        None, если маршрута, задачи или попытки нет.
        Ошибки: NotFoundError("USER_NOT_FOUND").
        """
        routing = await self._attempts.get_routing(self._session, attempt_id)
        if routing is None:
            return None
        task_id, user_id, provider = routing

        # порядок блокировок: пользователь -> задача -> попытка
        user = await self._ledger.lock_user(user_id)
        task = await self._tasks.get_for_update(self._session, task_id)
        attempt = await self._attempts.get_for_update(self._session, attempt_id)
        if task is None or attempt is None:
            return None
        return LockedAttempt(user, task, attempt, provider)

    async def advance(
        self,
        user: User,
        task: TaskModel,
        failed: AttemptModel,
        error_kind: ErrorKind,
        events: list[Event],
    ) -> None:
        """Ведёт running-задачу после неудачи: следующая нога или отказ с возвратом.

        Вызывать под блокировками пользователя и задачи.
        """
        if error_kind == ErrorKind.PAYLOAD:
            await self.fail_task(user, task, "payload", events)
            return

        model = await self._catalog.get_model(task.model_slug)
        # нога упавшей попытки есть всегда: FK не даёт удалить ногу с попытками
        failed_leg = next(leg for leg in model.legs if leg.id == failed.leg_id)
        leg, skipped = pick_next_leg(
            model.legs,
            failed_leg.priority,
            len(task.ref_images),
            error_kind == ErrorKind.MODERATION,
        )
        for skipped_leg in skipped:
            events.append(
                (
                    logging.DEBUG,
                    "leg_skipped task_id=%s leg_id=%s provider=%s reason=moderation",
                    (task.id, skipped_leg.id, skipped_leg.provider),
                )
            )
        if leg is None:
            await self.fail_task(user, task, "no_legs", events)
            return

        attempt_id = uuid4()
        await self._attempts.add(
            self._session, attempt_id, task.id, leg.id, seq=failed.seq + 1
        )
        events.append(
            (
                logging.DEBUG,
                "attempt_pending task_id=%s attempt_id=%s provider=%s seq=%s",
                (task.id, attempt_id, leg.provider, failed.seq + 1),
            )
        )

    async def fail_task(
        self, user: User, task: TaskModel, reason: str, events: list[Event]
    ) -> None:
        """Закрывает задачу как failed и возвращает цену один раз.

        Вызывать только при task.status == running под блокировкой задачи.
        """
        await self._tasks.finish(self._session, task, TaskStatus.FAILED, None)
        entry = await self._ledger.refund(user, task.id, task.price_charged)
        events.append(
            (
                logging.INFO,
                "task_failed task_id=%s user_id=%s reason=%s",
                (task.id, user.id, reason),
            )
        )
        events.append(
            (
                logging.INFO,
                "task_refunded task_id=%s user_id=%s amount=%s balance_after=%s",
                (task.id, user.id, task.price_charged, entry.balance_after),
            )
        )
