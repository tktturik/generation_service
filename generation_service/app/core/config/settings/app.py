from pydantic import Field

from app.core.config.settings.base import BaseAppSettings


class FastAPISettings(BaseAppSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    uc_log_level: str = Field(default="critical")
    workers: int = Field(default=4)
