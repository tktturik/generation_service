import logging

from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = find_dotenv(usecwd=False)
logger = logging.getLogger(__name__)


class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
