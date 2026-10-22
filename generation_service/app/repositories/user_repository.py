from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user_model import UserModel


class UserRepository:
    """Запросы к users. Не коммитит: транзакцией управляет вызывающий."""

    async def get_for_update(
        self, session: AsyncSession, user_id: int
    ) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.id == user_id).with_for_update()
        return await session.scalar(stmt)

    async def get_for_share(
        self, session: AsyncSession, user_id: int
    ) -> UserModel | None:
        stmt = (
            select(UserModel).where(UserModel.id == user_id).with_for_update(read=True)
        )
        return await session.scalar(stmt)

    async def add_balance(self, session: AsyncSession, user_id: int, delta: int) -> int:
        """Меняет баланс на delta и возвращает новый баланс.

        Строка должна существовать; уход баланса в минус отклоняет CHECK в БД.
        """
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(balance=UserModel.balance + delta)
            .returning(UserModel.balance)
        )
        return (await session.execute(stmt)).scalar_one()
