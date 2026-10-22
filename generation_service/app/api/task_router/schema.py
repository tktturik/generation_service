from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.types.attempt_types import AttemptStatus, ErrorKind
from app.core.types.model_types import Provider
from app.core.types.task_types import TaskStatus


class LegResponse(BaseModel):
    provider: Provider
    priority: int


class AttemptResponse(BaseModel):
    attempt_id: UUID
    provider: Provider
    status: AttemptStatus
    error_kind: ErrorKind | None
    created_at: datetime
    sent_at: datetime | None
    finished_at: datetime | None


class TaskResponse(BaseModel):
    task_id: UUID
    user_id: int
    model_slug: str
    status: TaskStatus
    result_url: str | None
    current_leg: LegResponse | None
    attempts: list[AttemptResponse]
