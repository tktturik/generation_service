import logging
from collections.abc import Callable
from time import time

from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next: Callable) -> None:
    """
    Middleware для логирования HTTP-запросов.
    """
    start_time = time()
    response = await call_next(request)
    process_time = time() - start_time
    logger.info(
        f'"{request.method} {request.url.path} HTTP/{request.scope["http_version"]}" '
        f'"from {getattr(request.client, "host", "unknown")} '
        f'"status - {response.status_code} time - {process_time:.3f}s"'
    )
    return response


def setup_middlewares(app: FastAPI) -> None:
    """
    Настраивает все middleware для приложения.
    """
    app.middleware("http")(log_requests)
