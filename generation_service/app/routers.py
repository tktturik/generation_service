from fastapi import APIRouter, FastAPI, status
from loguru import logger

from app.api.generate_router.router import generate_router
from app.api.payment_webhook_router.router import payment_webhook_router
from app.api.task_router.router import task_router
from app.api.user_router.router import user_router

health_router = APIRouter()


@health_router.get("/health", status_code=status.HTTP_204_NO_CONTENT)
async def health() -> None:
    """
    Проверка готовности сервиса. Наружу отдаём только статус, без деталей.
    """
    # Сюда добавлять проверки зависимостей (БД, кэш, внешние сервисы).
    # При провале логировать причину и поднимать HTTPException(status_code=503),
    # текст ошибки в ответ не передавать. Пример для БД:
    #     try:
    #         await session.execute(text("SELECT 1"))
    #     except Exception:
    #         logger.exception("Health: БД недоступна")
    #         raise HTTPException(status_code=503)


def get_routers() -> list[APIRouter]:
    """
    Возвращает список маршрутов для подключения к приложению.
    """
    return [
        health_router,
        generate_router,
        payment_webhook_router,
        task_router,
        user_router,
    ]


def setup_routers(app: FastAPI) -> None:
    """
    Подключает все маршруты к приложению и логирует их инициализацию.
    """
    for router in get_routers():
        app.include_router(router)
        # исправить
        logger.debug("Init router {}", getattr(router, "prefix", ""))
