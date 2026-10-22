from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.types.attempt_types import ErrorKind, WebhookOutcome, WebhookStatus


class ProviderWebhookRequest(BaseModel):
    attempt_id: UUID
    external_id: str = Field(min_length=1)
    status: WebhookStatus
    result_url: str | None = None
    error_kind: ErrorKind | None = None

    @model_validator(mode="after")
    def check_outcome_fields(self) -> Self:
        if self.status is WebhookStatus.COMPLETED and self.result_url is None:
            raise ValueError("completed требует result_url")
        if self.status is WebhookStatus.FAILED and self.error_kind is None:
            raise ValueError("failed требует error_kind")
        return self


class ProviderWebhookResponse(BaseModel):
    status: WebhookOutcome
