from typing import Annotated

from fastapi import APIRouter, Body, Path, Response

from fure.api.dependencies import ExecutionServiceDep, OptionalPrincipalDep
from fure.api.v1.execution import RUN_RESPONSES, WaitForRun, execute_function
from fure.api.v1.schemas import RunRequest, RunResponse
from fure.api.v1.schemas.common import FunctionName

router = APIRouter()


@router.post(
    "/{function_name}",
    summary="Run a function by name (alias)",
    response_model=RunResponse,
    responses=RUN_RESPONSES,
)
async def run_function(
    function_name: Annotated[FunctionName, Path(examples=["greet"])],
    request: Annotated[RunRequest, Body(examples=[{"input": {"name": "world"}}])],
    service: ExecutionServiceDep,
    response: Response,
    principal: OptionalPrincipalDep,
    wait: WaitForRun = True,
) -> RunResponse | Response:
    """Alias of POST /v1/functions/{function_id}/run, resolving the current name.

    Both routes execute the current revision with the same permissions. By default
    they wait for the result; wait=false returns 202 with the persisted run.
    """
    return await execute_function(
        function_name, request, service, response, principal, wait=wait
    )
