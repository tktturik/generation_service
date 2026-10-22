from app.core.config.settings.base import BaseAppSettings


class SecuritySettings(BaseAppSettings):
    provider_webhook_secret: str
    payment_webhook_secret: str
