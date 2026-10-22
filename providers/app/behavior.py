from fastapi import Request

from app.schemas import Behavior, ProviderName


class BehaviorStore:
    def __init__(self) -> None:
        self._behaviors: dict[ProviderName, Behavior] = {}
        self.reset()

    def get(self, name: ProviderName) -> Behavior:
        return self._behaviors[name]

    def set(self, name: ProviderName, behavior: Behavior) -> None:
        self._behaviors[name] = behavior

    def reset(self) -> None:
        self._behaviors = {name: Behavior() for name in ProviderName}


def get_behavior_store(request: Request) -> BehaviorStore:
    return request.app.state.behavior_store
