from pydantic import Field

from app.core.config.settings.base import BaseAppSettings


class LoggerSettings(BaseAppSettings):
    log_level: str = Field(default="DEBUG")
    log_file: str = Field(default="app.log")
    log_to_console: bool = Field(default=True)
