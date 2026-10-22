from collections.abc import Mapping, Sequence
from uuid import UUID

import httpx
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from app.core.types.attempt_types import SendOutcome, SendResult
from app.core.types.model_types import Provider


class TaskAccepted(BaseModel):
    external_id: str = Field(min_length=1)


def _parse_external_id(response: httpx.Response) -> str | None:
    # None означает неразборчивое тело или пустой external_id: вызывающий код считает это нарушением контракта
    try:
        return TaskAccepted.model_validate_json(response.content).external_id
    except ValidationError:
        return None


class ProviderClient:
    def __init__(self, client: httpx.AsyncClient, urls: Mapping[Provider, str]) -> None:
        self._client = client
        self._urls = urls

    async def send(
        self,
        provider: Provider,
        attempt_id: UUID,
        prompt: str,
        ref_images: Sequence[str],
    ) -> SendResult:
        payload = {
            "attempt_id": str(attempt_id),
            "prompt": prompt,
            "ref_images": list(ref_images),
        }
        try:
            response = await self._client.post(
                f"{self._urls[provider]}/tasks", json=payload
            )
        except httpx.TransportError:
            return SendResult(SendOutcome.TIMEOUT, None)

        if response.status_code >= 500:
            return SendResult(SendOutcome.REJECTED, None)
        if response.status_code == 202:
            external_id = _parse_external_id(response)
            if external_id is not None:
                return SendResult(SendOutcome.ACCEPTED, external_id)

        logger.error(
            "provider_contract_error attempt_id={} status_code={}",
            attempt_id,
            response.status_code,
        )
        return SendResult(SendOutcome.REJECTED, None)
