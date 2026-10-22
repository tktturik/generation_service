from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.model_model import ModelModel


class ModelRepository:
    """Запросы к models. Не коммитит: транзакцией управляет вызывающий."""

    async def get(self, session: AsyncSession, slug: str) -> ModelModel | None:
        stmt = select(ModelModel).where(ModelModel.slug == slug)
        return await session.scalar(stmt)
