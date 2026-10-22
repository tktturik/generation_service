import asyncio
import random
from uuid import UUID, uuid4

import httpx
from fastapi import Request
from loguru import logger

from app.behavior import BehaviorStore
from app.schemas import Behavior, Duplicate, ProviderName, SyncError, WebhookBody
from app.signature import sign

SYNC_TIMEOUT_SECONDS = 30
DELIVERY_TIMEOUT_SECONDS = 5
MAX_DELIVERY_RETRIES = 5
RETRY_PAUSE_SECONDS = 2
DELAY_MIN_SECONDS = 2
DELAY_MAX_SECONDS = 20


class TaskScheduler:
    def __init__(
        self,
        client: httpx.AsyncClient,
        behaviors: BehaviorStore,
        webhook_base_url: str,
        secret: str,
    ) -> None:
        self._client = client
        self._behaviors = behaviors
        self._webhook_base_url = webhook_base_url
        self._secret = secret
        self._tasks_by_attempt: dict[UUID, str] = {}
        self._background: set[asyncio.Task[None]] = set()

    async def accept(self, name: ProviderName, attempt_id: UUID) -> str | None:
        """Возвращает external_id или None при синхронном отказе (роут отвечает 503)."""
        behavior = self._behaviors.get(name)

        if behavior.sync_error is not SyncError.NONE:
            if behavior.sync_error is SyncError.TIMEOUT:
                await asyncio.sleep(SYNC_TIMEOUT_SECONDS)
            logger.info(
                "sync_error provider={} attempt_id={} mode={}",
                name,
                attempt_id,
                behavior.sync_error,
            )
            return None

        known_external_id = self._tasks_by_attempt.get(attempt_id)
        if known_external_id is not None:
            logger.info(
                "task_repeat provider={} attempt_id={} external_id={}",
                name,
                attempt_id,
                known_external_id,
            )
            return known_external_id

        external_id = f"{name}-{uuid4().hex}"
        self._tasks_by_attempt[attempt_id] = external_id
        webhook = self._build_webhook(behavior, attempt_id, external_id)
        delay = None if behavior.silent else self._pick_delay(behavior)

        if delay is not None:
            body = webhook.model_dump_json(exclude_none=True).encode()
            task = asyncio.create_task(
                self._run(name, attempt_id, body, delay, behavior.duplicate)
            )
            self._background.add(task)
            task.add_done_callback(self._background.discard)

        logger.info(
            "task_accepted provider={} attempt_id={} "
            "external_id={} outcome={} delay={}",
            name,
            attempt_id,
            external_id,
            webhook.status,
            delay,
        )
        return external_id

    def reset(self) -> None:
        for task in self._background:
            task.cancel()
        self._background.clear()
        self._tasks_by_attempt.clear()

    @staticmethod
    def _build_webhook(
        behavior: Behavior, attempt_id: UUID, external_id: str
    ) -> WebhookBody:
        if random.random() < behavior.fail_rate:
            return WebhookBody(
                attempt_id=attempt_id,
                external_id=external_id,
                status="failed",
                error_kind=behavior.error_kind,
            )
        return WebhookBody(
            attempt_id=attempt_id,
            external_id=external_id,
            status="completed",
            result_url=f"https://files.fake/{external_id}.png",
        )

    @staticmethod
    def _pick_delay(behavior: Behavior) -> float:
        if behavior.delay_seconds is not None:
            return behavior.delay_seconds
        return random.uniform(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS)

    async def _run(
        self,
        name: ProviderName,
        attempt_id: UUID,
        body: bytes,
        delay: float,
        duplicate: Duplicate,
    ) -> None:
        # План требует, чтобы сбой фоновой доставки не валил процесс.
        try:
            await asyncio.sleep(delay)
            if duplicate is Duplicate.CONCURRENT:
                await asyncio.gather(
                    self._deliver(name, attempt_id, body),
                    self._deliver(name, attempt_id, body),
                )
                return
            await self._deliver(name, attempt_id, body)
            if duplicate is Duplicate.SEQUENTIAL:
                await self._deliver(name, attempt_id, body)
        except Exception:
            logger.exception(
                "delivery_failed provider={} attempt_id={}", name, attempt_id
            )

    async def _deliver(self, name: ProviderName, attempt_id: UUID, body: bytes) -> None:
        url = f"{self._webhook_base_url}/webhooks/providers/{name}"
        headers = {
            "Content-Type": "application/json",
            "X-Signature": sign(self._secret, body),
        }
        for attempt_try in range(1, MAX_DELIVERY_RETRIES + 2):
            try:
                response = await self._client.post(
                    url,
                    content=body,
                    headers=headers,
                    timeout=DELIVERY_TIMEOUT_SECONDS,
                )
            except httpx.TransportError as exc:
                reason = type(exc).__name__
            else:
                if response.is_success:
                    logger.info(
                        "webhook_delivered attempt_id={} status_code={} try={}",
                        attempt_id,
                        response.status_code,
                        attempt_try,
                    )
                    return
                reason = f"status_{response.status_code}"
            logger.warning(
                "webhook_retry attempt_id={} try={} reason={}",
                attempt_id,
                attempt_try,
                reason,
            )
            await asyncio.sleep(RETRY_PAUSE_SECONDS)
        logger.warning("webhook_dropped attempt_id={}", attempt_id)


def get_task_scheduler(request: Request) -> TaskScheduler:
    return request.app.state.task_scheduler
