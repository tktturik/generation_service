from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_task_service
from app.api.generate_router.schema import GenerateRequest, GenerateResponse
from app.services.task_service import TaskService

generate_router = APIRouter(tags=["generate"])


@generate_router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate(
    payload: GenerateRequest,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> GenerateResponse:
    task_id = await service.create_task(
        payload.user_id, payload.model_slug, payload.prompt, payload.ref_images
    )
    return GenerateResponse(task_id=task_id)
