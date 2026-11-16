from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from fure.api.dependencies import AuthServiceDep, PrincipalDep
from fure.api.v1.schemas.auth import (
    APIKeyCreatedResponse,
    APIKeyCreateRequest,
    APIKeyResponse,
    key_response,
)
from fure.api.v1.schemas.common import PaginationRequest, PaginationResponse

router = APIRouter()


@router.get("")
async def list_keys(
    query: Annotated[PaginationRequest, Query()],
    principal: PrincipalDep,
    response: Response,
    service: AuthServiceDep,
) -> PaginationResponse[APIKeyResponse]:
    keys, total = await service.list_keys(principal, **query.model_dump())
    response.headers["Cache-Control"] = "no-store"
    return PaginationResponse(
        items=[key_response(key) for key in keys],
        total=total,
        page=query.page,
        size=query.size,
    )


@router.post("", status_code=201)
async def create_key(
    body: APIKeyCreateRequest,
    principal: PrincipalDep,
    response: Response,
    service: AuthServiceDep,
) -> APIKeyCreatedResponse:
    key, secret = await service.create_key(principal, **body.model_dump())
    response.headers["Cache-Control"] = "no-store"
    return APIKeyCreatedResponse(**key_response(key).model_dump(), secret=secret)


@router.delete("/{key_id}", status_code=204)
async def revoke_key(
    key_id: UUID, principal: PrincipalDep, service: AuthServiceDep
) -> Response:
    await service.revoke_key(principal, key_id)
    return Response(status_code=204)
