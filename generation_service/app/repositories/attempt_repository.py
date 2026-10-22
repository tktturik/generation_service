from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.attempt_model import AttemptModel
from app.database.models.model_leg_model import ModelLegModel
from app.database.models.task_model import TaskModel


class AttemptRepository:
    """Запросы к attempts. Не коммитит: транзакцией управляет вызывающий."""

    async def add(
        self,
        session: AsyncSession,
        attempt_id: UUID,
        task_id: UUID,
        leg_id: int,
        seq: int,
    ) -> AttemptModel:
        attempt = AttemptModel(
            id=attempt_id,
            task_id=task_id,
            leg_id=leg_id,
            seq=seq,
            status="pending",
        )
        session.add(attempt)
        await session.flush()
        # server_default-колонки после flush не загружены: чтение даст MissingGreenlet
        await session.refresh(
            attempt, attribute_names=["created_at", "lease_expirations"]
        )
        return attempt

    async def list_with_legs(
        self, session: AsyncSession, task_id: UUID
    ) -> list[tuple[AttemptModel, ModelLegModel]]:
        stmt = (
            select(AttemptModel, ModelLegModel)
            .join(ModelLegModel, ModelLegModel.id == AttemptModel.leg_id)
            .where(AttemptModel.task_id == task_id)
            .order_by(AttemptModel.seq)
        )
        return [(attempt, leg) for attempt, leg in (await session.execute(stmt)).all()]

    async def claim_pending(
        self, session: AsyncSession, limit: int, lease_seconds: int
    ) -> list[tuple[AttemptModel, TaskModel, ModelLegModel]]:
        # SKIP LOCKED: параллельные воркеры не берут одни и те же попытки
        ids_stmt = (
            select(AttemptModel.id)
            .where(AttemptModel.status == "pending")
            .order_by(AttemptModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        ids = list((await session.scalars(ids_stmt)).all())
        if not ids:
            return []
        await session.execute(
            update(AttemptModel)
            .where(AttemptModel.id.in_(ids))
            .values(
                status="sending",
                lease_until=func.now() + timedelta(seconds=lease_seconds),
            )
            .execution_options(synchronize_session=False)
        )
        stmt = (
            select(AttemptModel, TaskModel, ModelLegModel)
            .join(TaskModel, TaskModel.id == AttemptModel.task_id)
            .join(ModelLegModel, ModelLegModel.id == AttemptModel.leg_id)
            .where(AttemptModel.id.in_(ids))
            .order_by(AttemptModel.created_at)
            # объекты могли быть в identity map до UPDATE
            .execution_options(populate_existing=True)
        )
        return [
            (attempt, task, leg) for attempt, task, leg in await session.execute(stmt)
        ]

    async def mark_sent(
        self,
        session: AsyncSession,
        attempt_id: UUID,
        lease_until: datetime,
        external_id: str,
    ) -> bool:
        # условие по lease_until: если аренда истекла и попытку перехватили, отметка не пройдёт
        stmt = (
            update(AttemptModel)
            .where(
                AttemptModel.id == attempt_id,
                AttemptModel.status == "sending",
                AttemptModel.lease_until == lease_until,
            )
            .values(
                status="sent",
                external_id=external_id,
                sent_at=func.now(),
                lease_until=None,
            )
            .returning(AttemptModel.id)
            .execution_options(synchronize_session=False)
        )
        return (await session.scalar(stmt)) is not None

    async def get_routing(
        self, session: AsyncSession, attempt_id: UUID
    ) -> tuple[UUID, int, str] | None:
        stmt = (
            select(AttemptModel.task_id, TaskModel.user_id, ModelLegModel.provider)
            .join(TaskModel, TaskModel.id == AttemptModel.task_id)
            .join(ModelLegModel, ModelLegModel.id == AttemptModel.leg_id)
            .where(AttemptModel.id == attempt_id)
        )
        row = (await session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return row.task_id, row.user_id, row.provider

    async def get_for_update(
        self, session: AsyncSession, attempt_id: UUID
    ) -> AttemptModel | None:
        stmt = (
            select(AttemptModel)
            .where(AttemptModel.id == attempt_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return await session.scalar(stmt)

    async def finish(
        self,
        session: AsyncSession,
        attempt: AttemptModel,
        status: str,
        error_kind: str | None,
        external_id: str | None,
    ) -> None:
        attempt.status = status
        attempt.finished_at = func.now()  # type: ignore[assignment]  # SQL-выражение вместо значения, время берёт БД
        attempt.lease_until = None
        if error_kind is not None:
            attempt.error_kind = error_kind
        if external_id is not None and attempt.external_id is None:
            attempt.external_id = external_id
        await session.flush()
        await session.refresh(attempt, attribute_names=["finished_at"])

    async def supersede_live(
        self, session: AsyncSession, task_id: UUID, except_attempt_id: UUID
    ) -> list[UUID]:
        stmt = (
            update(AttemptModel)
            .where(
                AttemptModel.task_id == task_id,
                AttemptModel.status.in_(("pending", "sending", "sent")),
                AttemptModel.id != except_attempt_id,
            )
            .values(status="superseded", finished_at=func.now(), lease_until=None)
            .returning(AttemptModel.id)
            .execution_options(synchronize_session=False)
        )
        return list((await session.scalars(stmt)).all())
