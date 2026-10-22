import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NoSuitableLegError, NotFoundError, TooManyActiveTasksError
from app.core.types.attempt_types import (
    AttemptStatus,
    AttemptView,
    ErrorKind,
)
from app.core.types.model_types import ModelLeg, Provider
from app.core.types.task_types import TaskDetails, TaskStatus
from app.database.models.attempt_model import AttemptModel
from app.database.models.model_leg_model import ModelLegModel
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.task_repository import TaskRepository
from app.services.catalog_service import CatalogService, pick_first_leg
from app.services.ledger_service import LedgerService

logger = logging.getLogger(__name__)

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
