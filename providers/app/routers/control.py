from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.behavior import BehaviorStore, get_behavior_store
from app.scheduler import TaskScheduler, get_task_scheduler
from app.schemas import Behavior, ProviderName

router = APIRouter(prefix="/control")


def _parse_name(name: str) -> ProviderName:
    try:
        return ProviderName(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="unknown provider") from exc


@router.put("/{name}", status_code=204)
def set_behavior(
    name: str,
    behavior: Behavior,
    store: Annotated[BehaviorStore, Depends(get_behavior_store)],
) -> None:
    provider = _parse_name(name)
    store.set(provider, behavior)
    logger.info("control_set provider={}", provider)


@router.get("/{name}", response_model=Behavior)
def get_behavior(
    name: str,
    store: Annotated[BehaviorStore, Depends(get_behavior_store)],
) -> Behavior:
    return store.get(_parse_name(name))


@router.post("/reset", status_code=204)
def reset(
    store: Annotated[BehaviorStore, Depends(get_behavior_store)],
    scheduler: Annotated[TaskScheduler, Depends(get_task_scheduler)],
) -> None:
    store.reset()
    scheduler.reset()
    logger.info("control_reset")
