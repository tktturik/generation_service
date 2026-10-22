import asyncio
import hashlib
import hmac
import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
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
        await conn.execute(
            text("DELETE FROM attempts WHERE task_id IN (SELECT id FROM tasks WHERE user_id = :id)"),
            params,
        )
        await conn.execute(text("DELETE FROM tasks WHERE user_id = :id"), params)
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


@pytest_asyncio.fixture
async def providers_control() -> AsyncIterator[httpx.AsyncClient]:
    """Клиент к /control фейк-провайдеров; поведение сбрасывается до и после теста."""
    async with httpx.AsyncClient(base_url=os.environ["PROVIDERS_URL"]) as client:
        (await client.post("/control/reset")).raise_for_status()
        yield client
        (await client.post("/control/reset")).raise_for_status()


@pytest_asyncio.fixture
async def silent_providers(providers_control: httpx.AsyncClient) -> httpx.AsyncClient:
    """Оба провайдера принимают задачи и не шлют вебхук."""
    for name in ("alpha", "beta"):
        response = await providers_control.put(f"/control/{name}", json={"silent": True})
        response.raise_for_status()
    return providers_control


@pytest_asyncio.fixture
async def funded_user(
    user: int,
    signed_payment: tuple[bytes, dict[str, str]],
    http_client: httpx.AsyncClient,
) -> int:
    """Пользователь с балансом 10 после подписанного вебхука оплаты."""
    body, headers = signed_payment
    response = await http_client.post("/webhooks/payments", content=body, headers=headers)
    response.raise_for_status()
    return user


@pytest.fixture
def sign_provider_webhook() -> Callable[[dict[str, Any]], tuple[bytes, dict[str, str]]]:
    """Фабрика: тело вебхука провайдера -> (байты, заголовки с подписью HMAC-SHA256)."""

    def sign(payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
        body = json.dumps(payload).encode()
        secret = os.environ["PROVIDER_WEBHOOK_SECRET"].encode()
        signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
        return body, {"X-Signature": signature, "Content-Type": "application/json"}

    return sign


@pytest_asyncio.fixture
async def last_leg_task(
    funded_user: int,
    silent_providers: httpx.AsyncClient,
    http_client: httpx.AsyncClient,
    db_engine: AsyncEngine,
) -> tuple[UUID, UUID]:
    """Задача image-fast с 5 ссылками при молчащих провайдерах: (task_id, attempt_id)."""
    response = await http_client.post(
        "/generate",
        json={
            "user_id": funded_user,
            "model_slug": "image-fast",
            "prompt": f"prompt-{uuid4()}",
            "ref_images": [f"https://example.test/ref-{i}.png" for i in range(5)],
        },
    )
    response.raise_for_status()
    task_id = UUID(response.json()["task_id"])
    async with db_engine.connect() as conn:
        attempt_id = await conn.scalar(
            text("SELECT id FROM attempts WHERE task_id = :t ORDER BY seq DESC LIMIT 1"),
            {"t": task_id},
        )
    return task_id, attempt_id


@pytest_asyncio.fixture
async def alpha_fails_beta_completes(providers_control: httpx.AsyncClient) -> httpx.AsyncClient:
    """alpha всегда отвечает failed technical, beta завершает задачу; обоим задержка 1 с."""
    alpha = await providers_control.put(
        "/control/alpha",
        json={"fail_rate": 1, "error_kind": "technical", "delay_seconds": 1},
    )
    alpha.raise_for_status()
    beta = await providers_control.put("/control/beta", json={"delay_seconds": 1})
    beta.raise_for_status()
    return providers_control


@pytest_asyncio.fixture
async def first_leg_task(
    funded_user: int,
    alpha_fails_beta_completes: httpx.AsyncClient,
    http_client: httpx.AsyncClient,
) -> UUID:
    """Задача image-fast без ссылок (первая нога alpha) от пользователя с балансом 10."""
    response = await http_client.post(
        "/generate",
        json={
            "user_id": funded_user,
            "model_slug": "image-fast",
            "prompt": f"prompt-{uuid4()}",
        },
    )
    response.raise_for_status()
    return UUID(response.json()["task_id"])


@pytest.fixture
def wait_task_finished(
    http_client: httpx.AsyncClient,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Фабрика ожидания: опрос GET /tasks/{id} до статуса не running, дедлайн по умолчанию 30 с.

    Опрос с паузой - осознанное исключение из правил тестов (D68).
    """

    async def wait(task_id: UUID, deadline: float = 30) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        limit = loop.time() + deadline
        while True:
            response = await http_client.get(f"/tasks/{task_id}")
            response.raise_for_status()
            task = response.json()
            if task["status"] != "running":
                return task
            if loop.time() >= limit:
                pytest.fail(
                    f"задача {task_id} не завершилась за {deadline} с, статус {task['status']}"
                )
            await asyncio.sleep(0.5)

    return wait


@pytest_asyncio.fixture
async def timed_out_task(
    last_leg_task: tuple[UUID, UUID],
    wait_task_finished: Callable[..., Awaitable[dict[str, Any]]],
    db_engine: AsyncEngine,
) -> tuple[UUID, UUID, str]:
    """Задача, закрытая сторожем по таймауту провайдера: (task_id, attempt_id, external_id)."""
    task_id, attempt_id = last_leg_task
    await wait_task_finished(task_id, deadline=90)
    async with db_engine.connect() as conn:
        external_id = await conn.scalar(
            text("SELECT external_id FROM attempts WHERE id = :a"), {"a": attempt_id}
        )
    return task_id, attempt_id, external_id


@pytest.fixture
def late_completed_webhook(
    timed_out_task: tuple[UUID, UUID, str],
    sign_provider_webhook: Callable[[dict[str, Any]], tuple[bytes, dict[str, str]]],
) -> tuple[bytes, dict[str, str]]:
    """Подписанный поздний вебхук completed для попытки, уже закрытой сторожем."""
    _, attempt_id, external_id = timed_out_task
    return sign_provider_webhook(
        {
            "attempt_id": str(attempt_id),
            "external_id": external_id,
            "status": "completed",
            "result_url": f"https://example.test/result-{attempt_id}.png",
        }
    )
