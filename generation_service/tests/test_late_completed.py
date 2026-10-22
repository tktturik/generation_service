from uuid import UUID

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.e2e
async def test_late_completed_after_watchdog_is_ignored(
    http_client: httpx.AsyncClient,
    db_engine: AsyncEngine,
    funded_user: int,
    timed_out_task: tuple[UUID, UUID, str],
    late_completed_webhook: tuple[bytes, dict[str, str]],
) -> None:
    """Поздний completed после failed от сторожа игнорируется: один возврат, баланс 10."""
    task_id, _, _ = timed_out_task
    body, headers = late_completed_webhook

    response = await http_client.post("/webhooks/providers/beta", content=body, headers=headers)

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
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert task_status == "failed"
    assert refunds == 1
    assert balance == 10
