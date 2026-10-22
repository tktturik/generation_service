from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.dependencies import get_payment_service, verify_payment_signature
from app.api.payment_webhook_router.schema import (
    PaymentWebhookRequest,
    PaymentWebhookResponse,
)
from app.services.payment_service import PaymentService

payment_webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@payment_webhook_router.post("/payments")
async def payment_webhook(
    raw_body: Annotated[bytes, Depends(verify_payment_signature)],
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentWebhookResponse:
    # модели тела в сигнатуре нет: иначе FastAPI разберёт JSON до проверки подписи
    try:
        payload = PaymentWebhookRequest.model_validate_json(raw_body)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    outcome = await service.process_payment(
        payload.payment_id, payload.user_id, payload.tokens, payload.status
    )
    return PaymentWebhookResponse(status=outcome)
