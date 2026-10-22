from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.attempt_model import AttemptModel
from app.database.models.model_leg_model import ModelLegModel


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
