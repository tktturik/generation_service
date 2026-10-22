import uvicorn

from app.core.config import settings
from app.core.logging.log_conf import setup_logging

setup_logging()

if __name__ == "__main__":
    # Приложение передаётся строкой: uvicorn импортирует app.app только здесь,
    uvicorn.run(
        "app.app:create_app",
        factory=True,
        host=settings.api.host,
        port=settings.api.port,
        log_level=settings.api.uc_log_level,
    )
