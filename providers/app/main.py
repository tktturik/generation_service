from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI

from app.behavior import BehaviorStore
from app.config.log_conf import setup_logging
from app.config.settings import ProviderSettings
from app.routers import alpha, beta, control
from app.scheduler import DELIVERY_TIMEOUT_SECONDS, TaskScheduler


def create_app(settings: ProviderSettings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = httpx.AsyncClient(timeout=DELIVERY_TIMEOUT_SECONDS)
        behavior_store = BehaviorStore()
        task_scheduler = TaskScheduler(
            client,
            behavior_store,
            settings.WEBHOOK_BASE_URL,
            settings.PROVIDER_WEBHOOK_SECRET,
        )
        app.state.behavior_store = behavior_store
        app.state.task_scheduler = task_scheduler
        yield
        task_scheduler.reset()
        await client.aclose()

    app = FastAPI(lifespan=lifespan)
    app.include_router(alpha.router)
    app.include_router(beta.router)
    app.include_router(control.router)
    return app


if __name__ == "__main__":
    settings = ProviderSettings()
    setup_logging(settings.LOG_LEVEL)
    uvicorn.run(create_app(settings), host=settings.HOST, port=settings.PORT)
