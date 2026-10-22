from dataclasses import dataclass
from enum import StrEnum


class Provider(StrEnum):
    ALPHA = "alpha"
    BETA = "beta"


@dataclass(frozen=True, slots=True)
class ModelLeg:
    id: int
    priority: int
    provider: Provider
    max_ref_images: int
    skip_on_moderation: bool


@dataclass(frozen=True, slots=True)
class Model:
    slug: str
    price: int
    # ноги упорядочены по возрастанию priority
    legs: tuple[ModelLeg, ...]
