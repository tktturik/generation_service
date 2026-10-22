from pathlib import Path
from dotenv import load_dotenv


def pytest_configure(config):
    """Загружает .env.test ДО всех импортов."""
    env_path = Path(__file__).parent / ".env.test"
    load_dotenv(env_path, override=True)
