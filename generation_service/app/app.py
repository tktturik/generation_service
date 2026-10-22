import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI

from app.clients.provider_client import ProviderClient
from app.core.config import settings
from app.core.types.model_types import Provider
from app.database.session import create_engine, create_sessionmaker
from app.exc_handler import setup_exception_handlers
from app.middleware import setup_middlewares
from app.routers import setup_routers
from app.workers.outbox_worker import OutboxWorker
from app.workers.watchdog_worker import WatchdogWorker

logger = logging.getLogger(__name__)


async def startup(app: FastAPI) -> None:
    app.state.engine = create_engine(settings.db)
    app.state.sessionmaker = create_sessionmaker(app.state.engine)
    app.state.http = httpx.AsyncClient(timeout=settings.provider.provider_http_timeout)
    app.state.provider_client = ProviderClient(
        app.state.http,
        {
            Provider.ALPHA: settings.provider.alpha_url,
            Provider.BETA: settings.provider.beta_url,
        },
    )
    app.state.outbox_worker = OutboxWorker(
        app.state.sessionmaker, app.state.provider_client, settings.worker
    )
    app.state.outbox_task = asyncio.create_task(app.state.outbox_worker.run())
    app.state.watchdog_worker = WatchdogWorker(app.state.sessionmaker, settings.worker)
    app.state.watchdog_task = asyncio.create_task(app.state.watchdog_worker.run())
    logger.info("START Application pid=%s", os.getpid())


async def shutdown(app: FastAPI) -> None:
    app.state.outbox_task.cancel()
    app.state.watchdog_task.cancel()
    # отмена задач воркеров: ждём их завершения, CancelledError здесь штатен
    with suppress(asyncio.CancelledError):
        await app.state.outbox_task
    with suppress(asyncio.CancelledError):
        await app.state.watchdog_task
    await app.state.http.aclose()
    await app.state.engine.dispose()
    logger.info("FINISH Application pid=%s", os.getpid())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await startup(app)
    yield
    await shutdown(app)


def create_app() -> FastAPI:
    """
    Фабрика приложения.
    """
    app = FastAPI(lifespan=lifespan, redirect_slashes=False)
    setup_routers(app=app)
    setup_exception_handlers(app=app)
    setup_middlewares(app=app)
    return app
