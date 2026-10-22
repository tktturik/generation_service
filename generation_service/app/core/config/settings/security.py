from pydantic import Field

from app.core.config.settings.base import BaseAppSettings


class SecuritySettings(BaseAppSettings):
    provider_webhook_secret: str = Field(
        description="Secret for signing provider webhooks"
    )
    payment_webhook_secret: str = Field(
        default="default_payment_secret",
        description="Secret for signing payment webhooks",
    )
