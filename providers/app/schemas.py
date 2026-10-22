from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProviderName(StrEnum):
    ALPHA = "alpha"
    BETA = "beta"


class ErrorKind(StrEnum):
    TECHNICAL = "technical"
    MODERATION = "moderation"
    PAYLOAD = "payload"


class SyncError(StrEnum):
    NONE = "none"
    HTTP_503 = "503"
    TIMEOUT = "timeout"


class Duplicate(StrEnum):
    NONE = "none"
    SEQUENTIAL = "sequential"
    CONCURRENT = "concurrent"


class Behavior(BaseModel):
    model_config = ConfigDict(frozen=True)

    fail_rate: float = Field(default=0, ge=0, le=1)
    error_kind: ErrorKind = ErrorKind.TECHNICAL
    sync_error: SyncError = SyncError.NONE
    duplicate: Duplicate = Duplicate.NONE
    silent: bool = False
    delay_seconds: float | None = Field(default=None, ge=0)


class TaskRequest(BaseModel):
    attempt_id: UUID
    prompt: str
    ref_images: list[str]


class TaskAccepted(BaseModel):
    external_id: str


class WebhookBody(BaseModel):
    attempt_id: UUID
    external_id: str
    status: Literal["completed", "failed"]
    result_url: str | None = None
    error_kind: ErrorKind | None = None
