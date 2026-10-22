from pydantic import Field

from app.core.config.settings.base import BaseAppSettings


class DatabaseSettings(BaseAppSettings):
    db_host: str
    db_port: int = Field(default=5432)
    db_user: str
    db_password: str
    db_name: str

    @property
    def url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
