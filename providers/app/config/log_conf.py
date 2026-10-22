import logging
import sys
from types import FrameType

from loguru import logger

UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


class InterceptHandler(logging.Handler):
    """Перенаправляет стандартные логи (stdlib, uvicorn) в loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Поднимаемся по стеку мимо logging и loguru, чтобы в логе было место вызова
        frame: FrameType | None = sys._getframe(1)
        depth = 1
        while frame and (
            frame.f_code.co_filename == logging.__file__
            or "loguru" in frame.f_code.co_filename
        ):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(level: str) -> None:
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.NOTSET)
    for name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    logger.remove()
    logger.add(
        sys.stderr,
        format=(
            "[<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>] "
            "<level>{level: >8}</level> "
            "<level>{message}</level> "
            "({file}:{line})"
        ),
        level=level,
        backtrace=False,
        diagnose=False,
        enqueue=True,
    )
