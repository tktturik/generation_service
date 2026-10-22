from pydantic_settings import BaseSettings


class ProviderSettings(BaseSettings):
    WEBHOOK_BASE_URL: str = "http://localhost:8000"
    PROVIDER_WEBHOOK_SECRET: str = "provider-test-secret"
    HOST: str = "0.0.0.0"
    PORT: int = 9000
    LOG_LEVEL: str = "INFO"
