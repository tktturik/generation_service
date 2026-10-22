from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.model_leg_model import ModelLegModel


class ModelLegRepository:
    """Запросы к model_legs. Не коммитит: транзакцией управляет вызывающий."""

    async def list_by_model(
        self, session: AsyncSession, slug: str
    ) -> list[ModelLegModel]:
        stmt = (
            select(ModelLegModel)
            .where(ModelLegModel.model_slug == slug)
            .order_by(ModelLegModel.priority)
        )
        return list((await session.scalars(stmt)).all())
