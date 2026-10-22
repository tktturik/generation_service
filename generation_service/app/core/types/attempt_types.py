from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.core.types.model_types import ModelLeg


class AttemptStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class ErrorKind(StrEnum):
    TECHNICAL = "technical"
    MODERATION = "moderation"
    PAYLOAD = "payload"


@dataclass(frozen=True, slots=True)
class AttemptView:
    attempt_id: UUID
    leg: ModelLeg
    status: AttemptStatus
    error_kind: ErrorKind | None
    created_at: datetime
    sent_at: datetime | None
    finished_at: datetime | None
