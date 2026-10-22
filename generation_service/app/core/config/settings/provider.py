from pydantic import Field

from app.core.config.settings.base import BaseAppSettings


class ProviderSettings(BaseAppSettings):
    alpha_url: str = Field(default="http://localhost:8001")
    beta_url: str = Field(default="http://localhost:8002")
    provider_http_timeout: float = Field(
        default=5.0, description="Timeout for HTTP requests to providers in seconds"
    )
