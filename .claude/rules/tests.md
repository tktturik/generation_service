---
paths:
  - "tests/**"
---
# Tests

Each level checks what the cheaper level below cannot, and never repeats it. Write tests for plausible scenarios with the minimal values that expose them, not for every real value. Before adding a test, name the failure it catches that no existing test catches; if there is none, do not write it.

## Levels

- unit: the cheapest level, with the most cases. Domain logic over data: calculations, conversions, parsing, validation, pure functions. All input variants and boundaries are checked here. No I/O, no mocks of own code. Routers, services and repositories are not unit-tested.
- integration: a service or repository working with a real dependency (database, redis, queue). Dependencies not under test are mocked. Check what the integration allows and forbids: unique constraints, rollback, idempotency, redelivery, dangerous cases. Do not re-check boundaries or branches already covered by unit. If one test logically covers another scenario, skip the second.
- e2e: the public interface (HTTP API) on the real stack from fixtures; only third-party services outside the project are mocked. Per route: the basic scenarios, status codes and response shape, plus what is visible only end to end (uniqueness, idempotency). No parameter enumeration, variants are covered below. Error-to-HTTP mapping is checked through real routes; no separate test per exception, and no unit tests for error routes.

## Structure

- tests/<type>/<domain>/<layer>/ mirrors src/. Each source module gets a folder named after it: src/domain/security.py gives tests/unit/domain/security/.
- unit: one file per function, test_<function>.py, with several tests on different checks of that function.
- integration: services and repositories are split the same way, one folder per module, files per method or scenario group. A file about one dependency is named after it (test_postgres.py).
- e2e: one file per route, test_<route>.py; a router with several routes is split by route.
- Test file names are unique across the tree, or the project uses --import-mode=importlib; otherwise equal basenames in different folders collide.

## Fixtures

- Environment setup, mocks and test data live in fixtures; tests never build data inline and never define fixtures inside test files.
- Logic repeated between tests becomes a fixture. A fixture lives in the conftest.py of the lowest folder that contains all its users: used by one folder, that folder's conftest; shared wider, a higher level. Keep the nesting of fixtures.

## Test body

- Test behavior and the contract from the plan, not implementation details. One behavior per test; the name says what is checked and the expected outcome.
- Every test has a one-line docstring in Russian stating what it verifies.
- Arrange with fixtures, act in one call, assert on what is visible from outside (return value, response, state in the checked dependency). Assert the essentials, not every field.
- Plain and light: no loops or conditionals, no helpers that need their own tests.
- Tests are independent and order-agnostic. Test data is unique (uuid suffix); fixtures clean state.

## Parametrization

One scenario with different inputs is one parametrized test with a few representative values (empty, minimal, maximal, wrong format, values that really occur; one per class, not every type). Tests that differ only in values are merged.

## Async and config

- Follow the project's pytest config: asyncio mode, markers. Async tests carry @pytest.mark.asyncio unless the mode is auto.
- No real domains, hosts or secrets in tests; use test values from fixtures.

## Not allowed

Calling real external services, sleeping to wait, asserting on log text, depending on other tests.

## Example

```python
@pytest.mark.parametrize(
    ("prompt_eval_count", "expected"),
    [(8192 - 1024 + 1, True), (8192 - 1024 - 1, False)],
)
def test_is_truncated_by_prompt_budget(prompt_eval_count: int, expected: bool) -> None:
    """Усечение определяется границей бюджета промпта."""
    result = is_truncated(
        prompt_eval_count=prompt_eval_count, done_reason="stop", num_ctx=8192, num_predict=1024
    )

    assert result is expected
```
