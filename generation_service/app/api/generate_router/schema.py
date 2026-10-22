from uuid import UUID

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    user_id: int
    model_slug: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    ref_images: list[str] = []


class GenerateResponse(BaseModel):
    task_id: UUID
