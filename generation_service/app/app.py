import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.database.session import create_engine, create_sessionmaker
from app.exc_handler import setup_exception_handlers
from app.middleware import setup_middlewares
from app.routers import setup_routers

logger = logging.getLogger(__name__)


async def startup(app: FastAPI) -> None:
    app.state.engine = create_engine(settings.db)
    app.state.sessionmaker = create_sessionmaker(app.state.engine)
    logger.info("START Application pid=%s", os.getpid())


async def shutdown(app: FastAPI) -> None:
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
