from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from fure.core.function import FUNCTION_DESCRIPTION_MAX_LENGTH, FUNCTION_NAME_PATTERN

type FunctionName = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=FUNCTION_NAME_PATTERN.pattern),
]
type FunctionDescription = Annotated[
    str, Field(max_length=FUNCTION_DESCRIPTION_MAX_LENGTH)
]


class RequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaginationRequest(RequestSchema):
    page: int = Field(
        default=0,
        ge=0,
    )
    size: int = Field(
        default=100,
        ge=1,
        le=1000,
    )


class PaginationResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int


class ErrorResponse(BaseModel):
    detail: str | list[dict[str, JsonValue]]
