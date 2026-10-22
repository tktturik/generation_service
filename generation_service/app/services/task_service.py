import logging
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NoSuitableLegError, NotFoundError, TooManyActiveTasksError
from app.core.types.attempt_types import (
    AttemptStatus,
    AttemptView,
    ErrorKind,
    WebhookOutcome,
    WebhookStatus,
)
from app.core.types.model_types import ModelLeg, Provider
from app.core.types.task_types import TaskDetails, TaskStatus
from app.core.types.user_types import User
from app.database.models.attempt_model import AttemptModel
from app.database.models.model_leg_model import ModelLegModel
from app.database.models.task_model import TaskModel
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.task_repository import TaskRepository
from app.services.catalog_service import (
    CatalogService,
    pick_first_leg,
    pick_next_leg,
)
from app.services.ledger_service import LedgerService

logger = logging.getLogger(__name__)

# отложенное событие лога: (уровень, шаблон, аргументы); пишется после коммита
_Event = tuple[int, str, tuple[object, ...]]

MAX_RUNNING_TASKS = 3

LIVE_ATTEMPT_STATUSES = frozenset(
    {AttemptStatus.PENDING, AttemptStatus.SENDING, AttemptStatus.SENT}
)


class TaskService:
    """Задачи: одна транзакция на вызов."""

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

    async def create_task(
        self, user_id: int, model_slug: str, prompt: str, ref_images: list[str]
    ) -> UUID:
        """Списывает токены, создаёт задачу и первую попытку в одной транзакции.

        Ошибки: NotFoundError("MODEL_NOT_FOUND" / "USER_NOT_FOUND"),
        NoSuitableLegError, TooManyActiveTasksError, InsufficientTokensError.
        """
        async with self._session.begin():
            model = await self._catalog.get_model(model_slug)
            leg = pick_first_leg(model.legs, len(ref_images))
            if leg is None:
                raise NoSuitableLegError()

            # пользователь блокируется первым из строк, меняемых в транзакции;
            # до этого его нельзя загружать: charge опирается на свежий баланс
            user = await self._ledger.lock_user(user_id)
            running = await self._tasks.count_running(self._session, user_id)
            if running >= MAX_RUNNING_TASKS:
                raise TooManyActiveTasksError()

            task_id = uuid4()
            await self._tasks.add(
                self._session,
                task_id,
                user_id,
                model_slug,
                prompt,
                ref_images,
                price_charged=model.price,
            )
            entry = await self._ledger.charge(user, task_id, model.price)

            attempt_id = uuid4()
            await self._attempts.add(self._session, attempt_id, task_id, leg.id, seq=1)

        # логи после выхода из транзакции: при откате ничего не пишем
        logger.info(
            "task_charged user_id=%s task_id=%s"
            "model_slug=%s amount=%s balance_after=%s",
            user_id,
            task_id,
            model_slug,
            model.price,
            entry.balance_after,
        )
        logger.debug(
            "attempt_pending task_id=%s attempt_id=%s provider=%s seq=%s",
            task_id,
            attempt_id,
            leg.provider,
            1,
        )
        return task_id

    async def get_task(self, task_id: UUID) -> TaskDetails:
        """Задача, текущая нога и попытки из одного снимка (задача FOR SHARE).

        Ошибки: NotFoundError("TASK_NOT_FOUND").
        """
        async with self._session.begin():
            task = await self._tasks.get_for_share(self._session, task_id)
            if task is None:
                raise NotFoundError("TASK_NOT_FOUND", f"Task {task_id} not found")
            rows = await self._attempts.list_with_legs(self._session, task_id)
            # ORM-поля читаем внутри транзакции: после commit они могут быть expired
            attempts = tuple(_to_attempt_view(attempt, leg) for attempt, leg in rows)
            return TaskDetails(
                task_id=task.id,
                user_id=task.user_id,
                model_slug=task.model_slug,
                status=TaskStatus(task.status),
                result_url=task.result_url,
                current_leg=_pick_current_leg(attempts),
                attempts=attempts,
            )

    async def fail_on_send(self, attempt_id: UUID, lease_until: datetime) -> None:
        """Закрывает попытку как technical после отказа или таймаута отправки.

        Устаревшая аренда или чужое состояние попытки: выход без изменений.
        """
        events: list[_Event] = []
        async with self._session.begin():
            routing = await self._attempts.get_routing(self._session, attempt_id)
            if routing is None:
                # изменений нет, лог до выхода безопасен
                logger.debug("attempt_send_stale attempt_id=%s", attempt_id)
                return
            task_id, user_id, _ = routing

            # порядок блокировок: пользователь -> задача -> попытка
            user = await self._ledger.lock_user(user_id)
            task = await self._tasks.get_for_update(self._session, task_id)
            attempt = await self._attempts.get_for_update(self._session, attempt_id)
            if (
                task is None
                or attempt is None
                or attempt.status != AttemptStatus.SENDING
                or attempt.lease_until != lease_until
            ):
                logger.debug("attempt_send_stale attempt_id=%s", attempt_id)
                return

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
                await self._advance(user, task, attempt, ErrorKind.TECHNICAL, events)

        # логи после выхода из транзакции: при откате ничего не пишем
        for level, message, args in events:
            logger.log(level, message, *args)

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
        events: list[_Event] = []
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
        events: list[_Event],
    ) -> WebhookOutcome:
        """Тело транзакции вебхука; логи только копит в events."""
        routing = await self._attempts.get_routing(self._session, attempt_id)
        if routing is None:
            events.append(
                (logging.WARNING, "webhook_unknown attempt_id=%s", (attempt_id,))
            )
            return WebhookOutcome.IGNORED
        task_id, user_id, leg_provider = routing
        if leg_provider != provider:
            events.append(
                (
                    logging.WARNING,
                    "webhook_provider_mismatch attempt_id=%s name=%s provider=%s",
                    (attempt_id, provider, leg_provider),
                )
            )
            return WebhookOutcome.IGNORED

        # порядок блокировок: пользователь -> задача -> попытка
        user = await self._ledger.lock_user(user_id)
        task = await self._tasks.get_for_update(self._session, task_id)
        attempt = await self._attempts.get_for_update(self._session, attempt_id)
        if task is None or attempt is None:
            events.append(
                (logging.WARNING, "webhook_unknown attempt_id=%s", (attempt_id,))
            )
            return WebhookOutcome.IGNORED

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
        await self._advance(user, task, attempt, kind, events)
        return WebhookOutcome.APPLIED

    async def _advance(
        self,
        user: User,
        task: TaskModel,
        failed: AttemptModel,
        error_kind: ErrorKind,
        events: list[_Event],
    ) -> None:
        """Ведёт running-задачу после неудачи: следующая нога или отказ с возвратом.

        Вызывать под блокировками пользователя и задачи.
        """
        if error_kind == ErrorKind.PAYLOAD:
            await self._fail_task(user, task, "payload", events)
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
            await self._fail_task(user, task, "no_legs", events)
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

    async def _fail_task(
        self, user: User, task: TaskModel, reason: str, events: list[_Event]
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


def _pick_current_leg(attempts: tuple[AttemptView, ...]) -> ModelLeg | None:
    """Нога живой попытки; без живой попытки нога последней по seq; без попыток None."""
    if not attempts:
        return None
    live = next(
        (attempt for attempt in attempts if attempt.status in LIVE_ATTEMPT_STATUSES),
        attempts[-1],
    )
    return live.leg


def _to_attempt_view(attempt: AttemptModel, leg: ModelLegModel) -> AttemptView:
    return AttemptView(
        attempt_id=attempt.id,
        leg=_to_leg(leg),
        status=AttemptStatus(attempt.status),
        error_kind=(
            ErrorKind(attempt.error_kind) if attempt.error_kind is not None else None
        ),
        created_at=attempt.created_at,
        sent_at=attempt.sent_at,
        finished_at=attempt.finished_at,
    )


def _to_leg(leg: ModelLegModel) -> ModelLeg:
    return ModelLeg(
        id=leg.id,
        priority=leg.priority,
        provider=Provider(leg.provider),
        max_ref_images=leg.max_ref_images,
        skip_on_moderation=leg.skip_on_moderation,
    )
