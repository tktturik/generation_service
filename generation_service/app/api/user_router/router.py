from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_user_service
from app.api.user_router.schema import UserBalanceResponse
from app.services.user_service import UserService

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.get("/{user_id}/balance")
async def get_user_balance(
    user_id: int,
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserBalanceResponse:
    balance = await service.get_balance(user_id)
    return UserBalanceResponse.model_validate(balance, from_attributes=True)
