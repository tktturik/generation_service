from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.core.types.attempt_types import AttemptView
from app.core.types.model_types import ModelLeg


class TaskStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TaskDetails:
    task_id: UUID
    user_id: int
    model_slug: str
    status: TaskStatus
    result_url: str | None
    current_leg: ModelLeg | None
    # попытки упорядочены по seq
    attempts: tuple[AttemptView, ...]
