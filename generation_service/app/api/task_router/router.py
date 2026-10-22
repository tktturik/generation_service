from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_task_service
from app.api.task_router.schema import (
    AttemptResponse,
    LegResponse,
    TaskResponse,
)
from app.core.types.task_types import TaskDetails
from app.services.task import TaskService

task_router = APIRouter(prefix="/tasks", tags=["tasks"])


@task_router.get("/{task_id}")
async def get_task(
    task_id: UUID,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    details = await service.get_task(task_id)
    return _to_response(details)


def _to_response(details: TaskDetails) -> TaskResponse:
    return TaskResponse(
        task_id=details.task_id,
        user_id=details.user_id,
        model_slug=details.model_slug,
        status=details.status,
        result_url=details.result_url,
        current_leg=(
            LegResponse(
                provider=details.current_leg.provider,
                priority=details.current_leg.priority,
            )
            if details.current_leg is not None
            else None
        ),
        attempts=[
            AttemptResponse(
                attempt_id=attempt.attempt_id,
                provider=attempt.leg.provider,
                status=attempt.status,
                error_kind=attempt.error_kind,
                created_at=attempt.created_at,
                sent_at=attempt.sent_at,
                finished_at=attempt.finished_at,
            )
            for attempt in details.attempts
        ],
    )
