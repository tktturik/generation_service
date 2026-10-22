from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.task_model import TaskModel


class TaskRepository:
    """Запросы к tasks. Не коммитит: транзакцией управляет вызывающий."""

    async def count_running(self, session: AsyncSession, user_id: int) -> int:
        # фильтр совпадает с предикатом частичного индекса ix_tasks_user_id_running
        stmt = (
            select(func.count())
            .select_from(TaskModel)
            .where(TaskModel.user_id == user_id, TaskModel.status == "running")
        )
        return (await session.execute(stmt)).scalar_one()

    async def add(
        self,
        session: AsyncSession,
        task_id: UUID,
        user_id: int,
        model_slug: str,
        prompt: str,
        ref_images: list[str],
        price_charged: int,
    ) -> TaskModel:
        task = TaskModel(
            id=task_id,
            user_id=user_id,
            model_slug=model_slug,
            prompt=prompt,
            ref_images=ref_images,
            price_charged=price_charged,
            status="running",
        )
        session.add(task)
        # строка нужна до записи журнала: ledger_entries.task_id ссылается на tasks.id
        await session.flush()
        return task

    async def get_for_share(
        self, session: AsyncSession, task_id: UUID
    ) -> TaskModel | None:
        stmt = (
            select(TaskModel).where(TaskModel.id == task_id).with_for_update(read=True)
        )
        return await session.scalar(stmt)
