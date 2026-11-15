from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, model_validator

from fure.api.v1.schemas.common import PaginationRequest, RequestSchema
from fure.api.v1.schemas.implementation import (
    ImplementationRequest,
    ImplementationResponse,
    PythonImplementationRequest,
)
from fure.api.v1.schemas.runner import (
    InlinePythonRunnerOptionsRequest,
    RunnerOptionsRequest,
    RunnerOptionsResponse,
)


class RevisionCreateRequest(RequestSchema):
    function_id: UUID
    implementation: ImplementationRequest
    runner_options: RunnerOptionsRequest

    @model_validator(mode="after")
    def validate_runner_compatibility(self) -> Self:
        python_implementation = isinstance(
            self.implementation, PythonImplementationRequest
        )
        python_runner = isinstance(
            self.runner_options, InlinePythonRunnerOptionsRequest
        )
        if python_implementation != python_runner:
            raise ValueError("'implementation' and 'runner_options' must be compatible")
        return self


class RevisionListRequest(PaginationRequest):
    function_id: UUID | None = None


class RevisionResponse(BaseModel):
    id: UUID
    function_id: UUID
    implementation: ImplementationResponse
    runner_options: RunnerOptionsResponse
    created_at: AwareDatetime
