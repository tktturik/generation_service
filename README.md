# FastAPI Backend Starter

Базовый шаблон сервиса с FastAPI, трейсингом, логированием и метриками.

## Инициализация

```sh
python3 -m venv .venv
source .venv/bin/activate  # На Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip freeze > requirements.txt
pip install -r requirements-dev.txt
pip freeze > requirements-dev.txt
pre-commit install
cp .env.example > .env
```

## Запуск локально

```sh
python src/main.py
```

## Разработка

Базовые команды:
```sh
ruff check .              # Линтинг
ruff format .             # Форматирование
mypy src/                 # Проверка типов
pytest tests/unit-tests   # Юнит-тесты
pre-commit run --all-files # Все проверки вручную
```

**Примечание:** ruff, ruff-format, mypy и unit-тесты запускаются автоматически при `git commit` через pre-commit hooks (`.pre-commit-config.yaml`). Вышеуказанные команды нужны для быстрой проверки перед коммитом.

## Docker

### Прямой запуск контейнера

```bash
docker build -t python-base:latest .
docker run -d --rm -p 8000:8000 --env-file .env --name backend python-base:latest

# Остановка контейнера
docker stop backend
```

### docker-compose (рекомендуется)

```bash
docker compose up -d --build      # Запуск
docker compose logs -f            # Просмотр логов
docker compose down               # Остановка
```
