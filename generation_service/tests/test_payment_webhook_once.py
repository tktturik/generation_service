import asyncio
import json

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.e2e
async def test_concurrent_identical_payment_webhooks_credit_once(
    http_client: httpx.AsyncClient,
    db_engine: AsyncEngine,
    user: int,
    signed_payment: tuple[bytes, dict[str, str]],
) -> None:
    """20 одновременных одинаковых вебхуков оплаты дают одно начисление."""
    body, headers = signed_payment
    payment_id = json.loads(body)["payment_id"]
    tokens = json.loads(body)["tokens"]

    responses = await asyncio.gather(
        *[http_client.post("/webhooks/payments", content=body, headers=headers) for _ in range(20)]
    )

    async with db_engine.connect() as conn:
        payments = await conn.scalar(
            text("SELECT count(*) FROM payments WHERE payment_id = :p"), {"p": payment_id}
        )
        entries = await conn.scalar(
            text(
                "SELECT count(*) FROM ledger_entries "
                "WHERE payment_id = :p AND kind = 'payment'"
            ),
            {"p": payment_id},
        )
        balance = await conn.scalar(text("SELECT balance FROM users WHERE id = :u"), {"u": user})
    assert {r.status_code for r in responses} == {200}
    assert payments == 1
    assert entries == 1
    assert balance == tokens
