from pydantic import BaseModel, Field

from app.core.types.payment_types import PaymentOutcome


class PaymentWebhookRequest(BaseModel):
    payment_id: str = Field(min_length=1)
    user_id: int
    tokens: int = Field(gt=0)
    status: str


class PaymentWebhookResponse(BaseModel):
    status: PaymentOutcome
