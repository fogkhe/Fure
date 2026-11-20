from typing import Annotated, Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, field_validator

from fure.api.v1.schemas.common import RequestSchema
from fure.core.runners.jinja.openai import DEFAULT_MAX_STEPS, DEFAULT_MAX_TOOL_CALLS

type Timeout = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class InlinePythonRunnerOptionsRequest(RequestSchema):
    type: Literal["inline_python"]
    timeout: Timeout | None = None


class OpenAIJinjaRunnerOptionsRequest(RequestSchema):
    type: Literal["openai_jinja"]
    timeout: Timeout | None = None
    api_key: SecretStr | None = None
    base_url: AnyHttpUrl
    model: str = Field(min_length=1)
    structured_outputs: bool = True
    reasoning_end_tags: list[
        Annotated[str, Field(min_length=1, max_length=256, pattern=r"\S")]
    ] = Field(default_factory=list, max_length=32)
    tool_function_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    max_steps: Annotated[int, Field(strict=True, ge=1)] | None = DEFAULT_MAX_STEPS
    max_tool_calls: Annotated[int, Field(strict=True, ge=0)] | None = (
        DEFAULT_MAX_TOOL_CALLS
    )

    @field_validator("tool_function_ids")
    @classmethod
    def unique_tool_functions(cls, ids: list[UUID]) -> list[UUID]:
        if len(set(ids)) != len(ids):
            raise ValueError("Tool functions must be unique")
        return ids


type RunnerOptionsRequest = Annotated[
    InlinePythonRunnerOptionsRequest | OpenAIJinjaRunnerOptionsRequest,
    Field(discriminator="type"),
]


class InlinePythonRunnerOptionsResponse(BaseModel):
    type: Literal["inline_python"]
    timeout: Timeout | None


class OpenAIJinjaRunnerOptionsResponse(BaseModel):
    type: Literal["openai_jinja"]
    timeout: Timeout | None
    base_url: AnyHttpUrl
    model: str
    structured_outputs: bool
    reasoning_end_tags: list[str]
    tool_function_ids: list[UUID]
    max_steps: int | None
    max_tool_calls: int | None


type RunnerOptionsResponse = Annotated[
    InlinePythonRunnerOptionsResponse | OpenAIJinjaRunnerOptionsResponse,
    Field(discriminator="type"),
]
