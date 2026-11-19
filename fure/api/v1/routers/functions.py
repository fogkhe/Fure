from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Query, Response, status

from fure.api.dependencies import (
    ExecutionServiceDep,
    FunctionServiceDep,
    PrincipalDep,
    require_permission,
)
from fure.api.v1.execution import RUN_RESPONSES, WaitForRun, execute_function
from fure.api.v1.presenters import function_response
from fure.api.v1.schemas import (
    ErrorResponse,
    FunctionCreateRequest,
    FunctionListRequest,
    FunctionResponse,
    FunctionUpdateRequest,
    PaginationResponse,
)
from fure.api.v1.schemas.run import RunRequest, RunResponse
from fure.core.auth import Permission
from fure.services.auth import require

router = APIRouter()


@router.get(
    "",
    summary="List functions",
    dependencies=[Depends(require_permission(Permission.FUNCTIONS_READ))],
)
async def list_functions(
    request: Annotated[FunctionListRequest, Query()],
    service: FunctionServiceDep,
) -> PaginationResponse[FunctionResponse]:
    """List functions, newest first. Deleted functions are excluded by default."""
    items, total = await service.list(**request.model_dump())
    return PaginationResponse(
        items=[function_response(item) for item in items],
        total=total,
        page=request.page,
        size=request.size,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.FUNCTIONS_CREATE))],
    summary="Create a function",
    responses={
        409: {"model": ErrorResponse, "description": "Function name is already in use"}
    },
)
async def create_function(
    request: Annotated[FunctionCreateRequest, Body()],
    service: FunctionServiceDep,
    principal: PrincipalDep,
) -> FunctionResponse:
    """Create a function without a revision. Create and select a revision before running it."""
    if request.public:
        require(principal, Permission.FUNCTIONS_PUBLISH)
    return function_response(await service.create(**request.model_dump()))


@router.get(
    "/{function_id}",
    summary="Get a function",
    dependencies=[Depends(require_permission(Permission.FUNCTIONS_READ))],
    responses={404: {"model": ErrorResponse, "description": "Function not found"}},
)
async def get_function(
    function_id: Annotated[UUID, Path()],
    service: FunctionServiceDep,
) -> FunctionResponse:
    return function_response(await service.get(function_id))


@router.patch(
    "/{function_id}",
    summary="Update a function or select its current revision",
    dependencies=[Depends(require_permission(Permission.FUNCTIONS_UPDATE))],
    responses={
        404: {"model": ErrorResponse, "description": "Function or revision not found"},
        409: {
            "model": ErrorResponse,
            "description": "Name conflict or revision belongs to another function",
        },
    },
)
async def update_function(
    function_id: Annotated[UUID, Path()],
    request: Annotated[FunctionUpdateRequest, Body()],
    service: FunctionServiceDep,
    principal: PrincipalDep,
) -> FunctionResponse:
    """Update supplied fields only. Null clears the description; other fields cannot be null.

    The selected revision must belong to this function. Implementation changes
    require a new revision. Use enabled to enable or disable execution.
    """
    if "public" in request.model_fields_set:
        require(principal, Permission.FUNCTIONS_PUBLISH)
    return function_response(
        await service.update(function_id, request.model_dump(exclude_unset=True))
    )


@router.delete(
    "/{function_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a function",
    dependencies=[Depends(require_permission(Permission.FUNCTIONS_DELETE))],
    responses={404: {"model": ErrorResponse, "description": "Function not found"}},
)
async def delete_function(
    function_id: Annotated[UUID, Path()],
    service: FunctionServiceDep,
) -> Response:
    """Mark a function as deleted, retaining its revisions and execution history."""
    await service.delete(function_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{function_id}/undelete",
    summary="Undelete a function",
    dependencies=[Depends(require_permission(Permission.FUNCTIONS_DELETE))],
    responses={
        404: {"model": ErrorResponse, "description": "Function not found"},
        409: {"model": ErrorResponse, "description": "Function name is already in use"},
    },
)
async def undelete_function(
    function_id: Annotated[UUID, Path()],
    service: FunctionServiceDep,
) -> FunctionResponse:
    """Clear the deletion marker, preserving the function's enabled flag and current revision."""
    return function_response(await service.undelete(function_id))


@router.post(
    "/{function_id}/run",
    summary="Run a function by ID",
    response_model=RunResponse,
    responses=RUN_RESPONSES,
)
async def run_function(
    function_id: Annotated[UUID, Path()],
    request: Annotated[RunRequest, Body(examples=[{"input": {"name": "world"}}])],
    service: ExecutionServiceDep,
    response: Response,
    principal: PrincipalDep,
    wait: WaitForRun = True,
) -> RunResponse | Response:
    """Execute the current revision by UUID and record the run.

    Authentication is required for all functions, including public ones. Return
    output, metadata and duration in seconds. With wait=false, return 202 with
    the persisted run immediately; runs.read is required.
    Poll /v1/runs/{run_id} for the result or POST its /cancel route to cancel it.
    """
    return await execute_function(
        function_id, request, service, response, principal, wait=wait
    )
