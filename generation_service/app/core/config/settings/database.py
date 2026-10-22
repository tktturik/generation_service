from pydantic import Field

from app.core.config.settings.base import BaseAppSettings


class DatabaseSettings(BaseAppSettings):
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5432)
    db_user: str = Field(default="postgres")
    db_password: str = Field(default="postgres")
    db_name: str = Field(default="generation_service")

    @property
    def url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
