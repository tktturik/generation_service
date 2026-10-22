from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.types.model_types import Model, ModelLeg, Provider
from app.database.models.model_leg_model import ModelLegModel
from app.repositories.model_leg_repository import ModelLegRepository
from app.repositories.model_repository import ModelRepository


def pick_first_leg(legs: Sequence[ModelLeg], ref_count: int) -> ModelLeg | None:
    """Первая нога по порядку legs, вмещающая ref_count образцов;
    legs уже упорядочены по priority."""
    return next((leg for leg in legs if leg.max_ref_images >= ref_count), None)


class CatalogService:
    """Каталог моделей. Транзакций не открывает:
    вызывается только внутри транзакции вызывающего."""

    def __init__(
        self,
        session: AsyncSession,
        models: ModelRepository,
        legs: ModelLegRepository,
    ) -> None:
        self._session = session
        self._models = models
        self._legs = legs

    async def get_model(self, slug: str) -> Model:
        """Модель с ногами по возрастанию priority; нет модели: NotFoundError."""
        model = await self._models.get(self._session, slug)
        if model is None:
            raise NotFoundError("MODEL_NOT_FOUND", f"Model {slug} not found")
        legs = await self._legs.list_by_model(self._session, slug)
        return Model(
            slug=model.slug,
            price=model.price,
            legs=tuple(_to_leg(leg) for leg in legs),
        )


def _to_leg(model: ModelLegModel) -> ModelLeg:
    return ModelLeg(
        id=model.id,
        priority=model.priority,
        provider=Provider(model.provider),
        max_ref_images=model.max_ref_images,
        skip_on_moderation=model.skip_on_moderation,
    )
