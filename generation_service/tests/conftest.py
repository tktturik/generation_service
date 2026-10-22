import hashlib
import hmac
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


def pytest_configure(config):
    """Загружает .env.test ДО всех импортов."""
    env_path = Path(__file__).parent / ".env.test"
    load_dotenv(env_path, override=True)


@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Движок БД стенда; закрывается по окончании сессии."""
    from app.core.config import DatabaseSettings
    from app.database.session import create_engine

    engine = create_engine(DatabaseSettings())
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    """HTTP-клиент к поднятому сервису, соединение закрывается после каждого запроса."""
    async with httpx.AsyncClient(
        base_url=os.environ["SERVICE_URL"],
        limits=httpx.Limits(max_connections=20),
        headers={"Connection": "close"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def user(db_engine: AsyncEngine) -> AsyncIterator[int]:
    """Пользователь с нулевым балансом; его строки удаляются после теста."""
    user_id = uuid4().int % (2**62)
    async with db_engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO users (id, balance) VALUES (:id, 0)"), {"id": user_id}
        )
    yield user_id
    async with db_engine.begin() as conn:
        params = {"id": user_id}
        await conn.execute(text("DELETE FROM ledger_entries WHERE user_id = :id"), params)
        await conn.execute(text("DELETE FROM payments WHERE user_id = :id"), params)
        await conn.execute(text("DELETE FROM users WHERE id = :id"), params)


@pytest_asyncio.fixture
async def signed_payment(user: int) -> tuple[bytes, dict[str, str]]:
    """Тело вебхука оплаты и заголовки с подписью HMAC-SHA256."""
    body = json.dumps(
        {
            "payment_id": f"pay-{uuid4()}",
            "user_id": user,
            "tokens": 10,
            "status": "succeeded",
        }
    ).encode()
    secret = os.environ["PAYMENT_WEBHOOK_SECRET"].encode()
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return body, {"X-Signature": signature, "Content-Type": "application/json"}
