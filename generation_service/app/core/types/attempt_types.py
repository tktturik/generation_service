from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.core.types.model_types import ModelLeg, Provider


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


class SendOutcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class SendResult:
    outcome: SendOutcome
    external_id: str | None


@dataclass(frozen=True, slots=True)
class ClaimedAttempt:
    attempt_id: UUID
    task_id: UUID
    provider: Provider
    prompt: str
    ref_images: tuple[str, ...]
    lease_until: datetime


class WebhookStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class WebhookOutcome(StrEnum):
    APPLIED = "applied"
    IGNORED = "ignored"


class OverdueKind(StrEnum):
    LEASE_EXPIRED = "lease_expired"
    PROVIDER_TIMEOUT = "provider_timeout"


@dataclass(frozen=True, slots=True)
class OverdueAttempt:
    attempt_id: UUID
    kind: OverdueKind
    # Заполнен только для OverdueKind.LEASE_EXPIRED:
    # по нему сторож проверяет, что аренда не сменилась
    lease_until: datetime | None
