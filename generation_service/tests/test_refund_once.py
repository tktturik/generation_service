import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.e2e
async def test_concurrent_failed_webhooks_on_last_leg_refund_once(
    http_client: httpx.AsyncClient,
    db_engine: AsyncEngine,
    funded_user: int,
    last_leg_task: tuple[UUID, UUID],
    sign_provider_webhook: Callable[[dict[str, Any]], tuple[bytes, dict[str, str]]],
) -> None:
    """10 одновременных failed technical на последней ноге дают один возврат."""
    task_id, attempt_id = last_leg_task
    body, headers = sign_provider_webhook(
        {
            "attempt_id": str(attempt_id),
            "external_id": f"ext-{attempt_id}",
            "status": "failed",
            "error_kind": "technical",
        }
    )

    responses = await asyncio.gather(
        *[
            http_client.post("/webhooks/providers/beta", content=body, headers=headers)
            for _ in range(10)
        ]
    )

    async with db_engine.connect() as conn:
        refunds = await conn.scalar(
            text("SELECT count(*) FROM ledger_entries WHERE task_id = :t AND kind = 'refund'"),
            {"t": task_id},
        )
        balance = await conn.scalar(
            text("SELECT balance FROM users WHERE id = :u"), {"u": funded_user}
        )
        task_status = await conn.scalar(
            text("SELECT status FROM tasks WHERE id = :t"), {"t": task_id}
        )
    outcomes = [r.json()["status"] for r in responses]
    assert {r.status_code for r in responses} == {200}
    assert outcomes.count("applied") == 1
    assert outcomes.count("ignored") == 9
    assert refunds == 1
    assert balance == 10
    assert task_status == "failed"
