from app.core.config.settings.base import BaseAppSettings


class WorkerSettings(BaseAppSettings):
    lease_seconds: int = 30
    outbox_poll_seconds: float = 1
    outbox_batch: int = 10
    max_lease_expirations: int = 3
    watchdog_poll_seconds: float = 5
    provider_timeout: int = 60
