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
    openapi_extra={"security": [{}]},
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

    Public functions can be run anonymously with wait=true. With wait=false,
    authentication and runs.read are required, and the persisted run is returned
    with status 202.
    """
    return await execute_function(
        function_name, request, service, response, principal, wait=wait
    )
