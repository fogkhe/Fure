from typing import Annotated

from fastapi import APIRouter, Body, Path, Response

from fure.api.dependencies import ExecutionServiceDep
from fure.api.v1.schemas import ErrorResponse, RunRequest, RunResponse
from fure.api.v1.schemas.common import FunctionName

router = APIRouter()


@router.post(
    "/{function_name}",
    summary="Run a function by name",
    responses={
        200: {
            "description": "Execution completed successfully",
            "headers": {
                "X-Run-Id": {
                    "description": "Persisted execution ID for /v1/runs/{run_id}",
                    "schema": {"type": "string", "format": "uuid"},
                }
            },
            "content": {
                "application/json": {
                    "example": {
                        "output": "Hello! How can I help you today?",
                        "meta": {
                            "input_tokens": 10,
                            "output_tokens": 261,
                            "total_tokens": 271,
                        },
                        "duration": 0.223,
                    }
                }
            },
        },
        404: {"model": ErrorResponse, "description": "Function not found or deleted"},
        409: {
            "model": ErrorResponse,
            "description": "Function is disabled, has no current revision, or execution was cancelled",
        },
        500: {"model": ErrorResponse, "description": "Function execution failed"},
        502: {"model": ErrorResponse, "description": "LLM provider request failed"},
        504: {"model": ErrorResponse, "description": "Execution timed out"},
    },
)
async def run_function(
    function_name: Annotated[FunctionName, Path(examples=["greet"])],
    request: Annotated[RunRequest, Body(examples=[{"input": {"name": "world"}}])],
    service: ExecutionServiceDep,
    response: Response,
) -> RunResponse:
    """Execute the function's current revision synchronously and record the run.

    Return output, runner metadata and duration in seconds. Omit input or use null
    for functions that take no input. Execution history is exposed through /v1/runs.
    """
    run = await service.execute(function_name, request.input)
    response.headers["X-Run-Id"] = str(run.id)
    return RunResponse.model_validate(run)
