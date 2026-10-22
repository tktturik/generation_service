from pydantic import Field

from app.core.config.settings.base import BaseAppSettings


class WorkerSettings(BaseAppSettings):
    lease_seconds: int = Field(
        default=30, description="Lease duration for processing tasks in seconds"
    )
    outbox_poll_seconds: float = Field(
        default=1.0, description="Polling interval for the outbox in seconds"
    )
    outbox_batch: int = Field(
        default=10, description="Number of tasks to fetch from the outbox in one batch"
    )
    max_lease_expirations: int = Field(
        default=3, description="Maximum number of times a lease can expire"
    )
    watchdog_poll_seconds: float = Field(
        default=5.0, description="Polling interval for the watchdog in seconds"
    )
    provider_timeout: int = Field(
        default=60, description="Timeout for HTTP requests to providers in seconds"
    )
