from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query

from fure.api.dependencies import ExecutionServiceDep, RunServiceDep
from fure.api.v1.presenters import run_response
from fure.api.v1.schemas import (
    ErrorResponse,
    PaginationResponse,
    RunDetailResponse,
    RunListRequest,
)

router = APIRouter()


@router.get("", summary="List execution history")
async def list_runs(
    request: Annotated[RunListRequest, Query()],
    service: RunServiceDep,
) -> PaginationResponse[RunDetailResponse]:
    """List runs, newest first, optionally filtered by function, revision and status."""
    items, total = await service.list(**request.model_dump())
    return PaginationResponse(
        items=[run_response(item) for item in items],
        total=total,
        page=request.page,
        size=request.size,
    )


@router.get(
    "/{run_id}",
    summary="Get a run",
    responses={404: {"model": ErrorResponse, "description": "Run not found"}},
)
async def get_run(
    run_id: Annotated[UUID, Path()],
    service: RunServiceDep,
) -> RunDetailResponse:
    """Get input, output, metadata, status and timestamps for a specific run."""
    return run_response(await service.get(run_id))


@router.post(
    "/{run_id}/cancel",
    summary="Cancel a pending or running execution",
    responses={
        404: {"model": ErrorResponse, "description": "Run not found"},
        409: {"model": ErrorResponse, "description": "Run has already finished"},
    },
)
async def cancel_run(
    run_id: Annotated[UUID, Path()],
    service: ExecutionServiceDep,
) -> RunDetailResponse:
    return run_response(await service.cancel(run_id))
