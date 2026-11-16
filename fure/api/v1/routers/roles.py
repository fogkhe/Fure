from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from fure.api.dependencies import AuthServiceDep, PrincipalDep
from fure.api.v1.schemas.auth import (
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
    role_response,
)
from fure.api.v1.schemas.common import PaginationRequest, PaginationResponse
from fure.core.auth import Permission

router = APIRouter()


@router.get("/permissions")
async def list_permissions(principal: PrincipalDep) -> list[Permission]:
    return list(Permission)


@router.get("")
async def list_roles(
    query: Annotated[PaginationRequest, Query()],
    principal: PrincipalDep,
    service: AuthServiceDep,
) -> PaginationResponse[RoleResponse]:
    roles, total = await service.list_roles(principal, **query.model_dump())
    return PaginationResponse(
        items=[role_response(role) for role in roles],
        total=total,
        page=query.page,
        size=query.size,
    )


@router.post("", status_code=201)
async def create_role(
    body: RoleCreateRequest, principal: PrincipalDep, service: AuthServiceDep
) -> RoleResponse:
    return role_response(await service.create_role(principal, **body.model_dump()))


@router.patch("/{role_id}")
async def update_role(
    role_id: UUID,
    body: RoleUpdateRequest,
    principal: PrincipalDep,
    service: AuthServiceDep,
) -> RoleResponse:
    return role_response(
        await service.update_role(
            principal, role_id, body.model_dump(exclude_unset=True)
        )
    )


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: UUID, principal: PrincipalDep, service: AuthServiceDep
) -> Response:
    await service.delete_role(principal, role_id)
    return Response(status_code=204)
