from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime, BaseModel, Field, JsonValue, Secret

from fure.api.dependencies import PrincipalDep, VariableServiceDep, require_permission
from fure.api.v1.schemas.common import (
    PaginationRequest,
    PaginationResponse,
    RequestSchema,
)
from fure.core.auth import Permission
from fure.services.auth import require
from fure.services.variables import VariableInfo

router = APIRouter()
type VariableName = Annotated[str, Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")]
manage = Depends(require_permission(Permission.VARIABLES_MANAGE))


class VariableUpdateRequest(RequestSchema):
    value: Secret[JsonValue]


class VariableCreateRequest(VariableUpdateRequest):
    name: VariableName
    secret: bool = False


class SecretVariableResponse(BaseModel):
    name: str
    secret: Literal[True] = True
    updated_at: AwareDatetime


class PlainVariableResponse(BaseModel):
    name: str
    secret: Literal[False] = False
    value: JsonValue
    updated_at: AwareDatetime


type VariableResponse = Annotated[
    PlainVariableResponse | SecretVariableResponse, Field(discriminator="secret")
]


def variable_response(info: VariableInfo) -> VariableResponse:
    if info.secret:
        return SecretVariableResponse(name=info.name, updated_at=info.updated_at)
    return PlainVariableResponse(
        name=info.name, value=info.value, updated_at=info.updated_at
    )


@router.get("")
async def list_variables(
    query: Annotated[PaginationRequest, Query()],
    principal: PrincipalDep,
    service: VariableServiceDep,
) -> PaginationResponse[VariableResponse]:
    if not principal.allows(Permission.VARIABLES_MANAGE):
        require(principal, Permission.VARIABLES_READ)
    items, total = await service.list(page=query.page, size=query.size)
    return PaginationResponse(
        items=[variable_response(item) for item in items],
        total=total,
        page=query.page,
        size=query.size,
    )


@router.post("", status_code=201, dependencies=[manage])
async def create_variable(
    body: VariableCreateRequest, service: VariableServiceDep
) -> VariableResponse:
    return variable_response(
        await service.create(
            body.name, body.value.get_secret_value(), secret=body.secret
        )
    )


@router.patch("/{name}", dependencies=[manage])
async def update_variable(
    name: VariableName, body: VariableUpdateRequest, service: VariableServiceDep
) -> VariableResponse:
    return variable_response(await service.replace(name, body.value.get_secret_value()))


@router.delete("/{name}", status_code=204, dependencies=[manage])
async def delete_variable(name: VariableName, service: VariableServiceDep) -> Response:
    await service.delete(name)
    return Response(status_code=204)
