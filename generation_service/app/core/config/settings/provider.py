from app.core.config.settings.base import BaseAppSettings


class ProviderSettings(BaseAppSettings):
    alpha_url: str
    beta_url: str
    provider_http_timeout: float = 5
