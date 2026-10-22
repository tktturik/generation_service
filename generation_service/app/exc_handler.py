import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import (
    AppError,
    InsufficientTokensError,
    InvalidSignatureError,
    NoSuitableLegError,
    NotFoundError,
    TooManyActiveTasksError,
)

logger = logging.getLogger(__name__)

_STATUS_BY_ERROR: dict[type[AppError], int] = {
    NotFoundError: 404,
    NoSuitableLegError: 400,
    InsufficientTokensError: 402,
    TooManyActiveTasksError: 429,
    InvalidSignatureError: 401,
}


def _status_for(exc: AppError) -> int:
    """
    Статус по ближайшему классу из словаря;
    для неизвестного подкласса AppError отдаёт 500.
    """
    for cls in type(exc).__mro__:
        if cls in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[cls]
    return 500


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Настраивает обработчики исключений для приложения.
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        # Ожидаемые ошибки не логируем: это не сбой сервиса (D35)
        return JSONResponse(
            status_code=_status_for(exc),
            content={"code": exc.code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def all_exception_handler_v2(
        request: Request, exc: Exception
    ) -> JSONResponse:
        msg = (
            f"Unhandled {exc.__class__.__name__} in API endpoint\n"
            f"API endpoint: {request.url.path}\n"
            f"Method: {request.method}"
        )
        request.state._exception_handled = True

        logger.exception(msg)

        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "Internal error",
            },
        )
