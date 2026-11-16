from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from fure.api.dependencies import AuthServiceDep, PrincipalDep
from fure.api.v1.schemas.auth import (
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
    user_response,
)
from fure.api.v1.schemas.common import PaginationRequest, PaginationResponse

router = APIRouter()


@router.get("")
async def list_users(
    query: Annotated[PaginationRequest, Query()],
    principal: PrincipalDep,
    service: AuthServiceDep,
) -> PaginationResponse[UserResponse]:
    users, total = await service.list_users(principal, **query.model_dump())
    return PaginationResponse(
        items=[user_response(user) for user in users],
        total=total,
        page=query.page,
        size=query.size,
    )


@router.post("", status_code=201)
async def create_user(
    body: UserCreateRequest, principal: PrincipalDep, service: AuthServiceDep
) -> UserResponse:
    fields = body.model_dump()
    fields["password"] = body.password.get_secret_value()
    return user_response(await service.create_user(principal, **fields))


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    body: UserUpdateRequest,
    principal: PrincipalDep,
    service: AuthServiceDep,
) -> UserResponse:
    fields = body.model_dump(exclude_unset=True)
    if body.password is not None:
        fields["password"] = body.password.get_secret_value()
    return user_response(await service.update_user(principal, user_id, fields))
