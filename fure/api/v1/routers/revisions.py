from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Path, Query, status

from fure.api.dependencies import RevisionServiceDep
from fure.api.v1.presenters import revision_response
from fure.api.v1.schemas import (
    ErrorResponse,
    PaginationResponse,
    RevisionCreateRequest,
    RevisionListRequest,
    RevisionResponse,
)
from fure.core.implementations import JinjaImplementation, PythonImplementation
from fure.core.runners.jinja.openai import OpenAIJinjaRunnerOptions
from fure.core.runners.python.inline import InlinePythonRunnerOptions
from fure.services.errors import InvalidInput

router = APIRouter()


@router.get("", summary="List revisions")
async def list_revisions(
    request: Annotated[RevisionListRequest, Query()],
    service: RevisionServiceDep,
) -> PaginationResponse[RevisionResponse]:
    """List immutable revisions, newest first. Filter by function_id for a function's version history."""
    items, total = await service.list(**request.model_dump())
    return PaginationResponse(
        items=[revision_response(item) for item in items],
        total=total,
        page=request.page,
        size=request.size,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create an immutable revision",
    responses={
        404: {"model": ErrorResponse, "description": "Function not found"},
        409: {"model": ErrorResponse, "description": "Function is deleted"},
    },
)
async def create_revision(
    request: Annotated[RevisionCreateRequest, Body()],
    service: RevisionServiceDep,
) -> RevisionResponse:
    """Create a version of the implementation and runner settings for an existing function.

    Python uses the inline_python runner; Jinja uses openai_jinja. Schemas for
    Python are inferred from function annotations. Jinja's input schema is inferred
    from its template; output_schema is supplied as-is for Structured Outputs.
    A new revision does not become current until selected through PATCH /v1/functions/{function_id}.
    API keys are accepted on creation and omitted from revision responses.
    """
    if request.implementation.type == "python":
        implementation = PythonImplementation(request.implementation.code)
    else:
        try:
            implementation = JinjaImplementation(
                request.implementation.template, request.implementation.output_schema
            )
        except ValueError as error:
            raise InvalidInput("Invalid Jinja template") from error
    options = request.runner_options
    if options.type == "inline_python":
        runner_options = InlinePythonRunnerOptions(timeout=options.timeout)
    else:
        runner_options = OpenAIJinjaRunnerOptions(
            timeout=options.timeout,
            api_key=options.api_key.get_secret_value()
            if options.api_key is not None
            else None,
            base_url=str(options.base_url),
            model=options.model,
        )
    return revision_response(
        await service.create(
            function_id=request.function_id,
            implementation=implementation,
            runner_options=runner_options,
        )
    )


@router.get(
    "/{revision_id}",
    summary="Get a revision",
    responses={404: {"model": ErrorResponse, "description": "Revision not found"}},
)
async def get_revision(
    revision_id: Annotated[UUID, Path()],
    service: RevisionServiceDep,
) -> RevisionResponse:
    return revision_response(await service.get(revision_id))
