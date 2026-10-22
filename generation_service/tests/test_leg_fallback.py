from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.e2e
async def test_first_leg_failure_falls_back_to_second_leg(
    db_engine: AsyncEngine,
    funded_user: int,
    first_leg_task: UUID,
    wait_task_finished: Callable[[UUID], Awaitable[dict[str, Any]]],
) -> None:
    """Отказ alpha переводит задачу на beta: две попытки, один charge, без refund."""
    task = await wait_task_finished(first_leg_task)

    async with db_engine.connect() as conn:
        kinds = (
            await conn.scalars(
                text("SELECT kind FROM ledger_entries WHERE task_id = :t"),
                {"t": first_leg_task},
            )
        ).all()
        balance = await conn.scalar(
            text("SELECT balance FROM users WHERE id = :u"), {"u": funded_user}
        )
    attempts = [(a["provider"], a["status"], a["error_kind"]) for a in task["attempts"]]
    assert task["status"] == "completed"
    assert task["current_leg"]["provider"] == "beta"
    assert ("alpha", "failed", "technical") in attempts
    assert ("beta", "completed", None) in attempts
    assert len(attempts) == 2
    assert kinds.count("charge") == 1
    assert kinds.count("refund") == 0
    assert balance == 8
