import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.provider_client import ProviderClient
from app.core.types.attempt_types import ClaimedAttempt, SendOutcome
from app.core.types.model_types import Provider
from app.repositories.attempt_repository import AttemptRepository
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


class OutboxService:
    def __init__(
        self,
        session: AsyncSession,
        attempts: AttemptRepository,
        client: ProviderClient,
        tasks: TaskService,
    ) -> None:
        self._session = session
        self._attempts = attempts
        self._client = client
        self._tasks = tasks

    async def claim_batch(self, limit: int, lease_seconds: int) -> list[ClaimedAttempt]:
        async with self._session.begin():
            rows = await self._attempts.claim_pending(
                self._session, limit, lease_seconds
            )
            claimed: list[ClaimedAttempt] = []
            for attempt, task, leg in rows:
                # claim_pending выставляет lease_until в том же запросе
                assert attempt.lease_until is not None
                claimed.append(
                    ClaimedAttempt(
                        attempt_id=attempt.id,
                        task_id=task.id,
                        provider=Provider(leg.provider),
                        prompt=task.prompt,
                        ref_images=tuple(task.ref_images),
                        lease_until=attempt.lease_until,
                    )
                )

        for item in claimed:
            logger.debug(
                "attempt_sending attempt_id=%s task_id=%s provider=%s",
                item.attempt_id,
                item.task_id,
                item.provider,
            )
        return claimed

    async def dispatch(self, claimed: ClaimedAttempt) -> None:
        # HTTP строго вне транзакции
        result = await self._client.send(
            claimed.provider,
            claimed.attempt_id,
            claimed.prompt,
            claimed.ref_images,
        )
        if result.outcome is not SendOutcome.ACCEPTED or result.external_id is None:
            await self._tasks.fail_on_send(claimed.attempt_id, claimed.lease_until)
            return

        async with self._session.begin():
            marked = await self._attempts.mark_sent(
                self._session,
                claimed.attempt_id,
                claimed.lease_until,
                result.external_id,
            )
        if marked:
            logger.debug(
                "attempt_sent attempt_id=%s task_id=%s",
                claimed.attempt_id,
                claimed.task_id,
            )
        else:
            logger.debug(
                "attempt_send_stale attempt_id=%s task_id=%s",
                claimed.attempt_id,
                claimed.task_id,
            )
