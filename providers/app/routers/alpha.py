from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.scheduler import TaskScheduler, get_task_scheduler
from app.schemas import ProviderName, TaskAccepted, TaskRequest

router = APIRouter(prefix="/alpha")


@router.post(
    "/tasks", status_code=status.HTTP_202_ACCEPTED, response_model=TaskAccepted
)
async def create_task(
    body: TaskRequest,
    scheduler: Annotated[TaskScheduler, Depends(get_task_scheduler)],
) -> TaskAccepted:
    external_id = await scheduler.accept(ProviderName.ALPHA, body.attempt_id)
    if external_id is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return TaskAccepted(external_id=external_id)
