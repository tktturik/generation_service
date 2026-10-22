from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.dependencies import get_task_service, verify_provider_signature
from app.api.provider_webhook_router.schema import (
    ProviderWebhookRequest,
    ProviderWebhookResponse,
)
from app.core.types.model_types import Provider
from app.services.task_service import TaskService

provider_webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@provider_webhook_router.post("/providers/{name}")
async def provider_webhook(
    name: Provider,
    raw_body: Annotated[bytes, Depends(verify_provider_signature)],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> ProviderWebhookResponse:
    # модели тела в сигнатуре нет: иначе FastAPI разберёт JSON до проверки подписи
    try:
        payload = ProviderWebhookRequest.model_validate_json(raw_body)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    outcome = await service.apply_provider_webhook(
        name,
        payload.attempt_id,
        payload.external_id,
        payload.status,
        payload.result_url,
        payload.error_kind,
    )
    return ProviderWebhookResponse(status=outcome)
