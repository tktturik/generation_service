from __future__ import annotations

import logging
from typing import TypeVar

from app.core.config.settings import FastAPISettings, LoggerSettings

logger = logging.getLogger(__name__)

T = TypeVar("T")

SETTINGS_REGISTRY: tuple[type, ...] = (FastAPISettings, LoggerSettings)


class SettingsContainer:
    """
    - Создаёт инстанс ровно один раз при первом обращении.
    - Даёт доступ по имени класса: settings.get(LoggerSettings) или
      settings.logger / settings.api
    """

    def __init__(self, registry: tuple[type, ...] = SETTINGS_REGISTRY) -> None:
        self._registry = registry
        self._instances: dict[type, object] = {}
        self._logged = False

    def get(self, cls: type[T]) -> T:
        if cls not in self._instances:
            instance = cls()
            self._instances[cls] = instance
        return self._instances[cls]  # type: ignore[return-value]

    def all(self) -> dict[type, object]:
        for cls in self._registry:
            self.get(cls)
        return dict(self._instances)

    @property
    def api(self) -> FastAPISettings:
        return self.get(FastAPISettings)

    @property
    def logger(self) -> LoggerSettings:
        return self.get(LoggerSettings)


settings = SettingsContainer()
