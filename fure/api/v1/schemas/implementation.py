from typing import Annotated, Literal

from pydantic import BaseModel, Field, JsonValue

from fure.api.v1.schemas.common import RequestSchema


class PythonImplementationRequest(RequestSchema):
    type: Literal["python"]
    code: str = Field(min_length=1)


class JinjaImplementationRequest(RequestSchema):
    type: Literal["jinja"]
    template: str
    output_schema: dict[str, JsonValue] = Field(default_factory=dict)


type ImplementationRequest = Annotated[
    PythonImplementationRequest | JinjaImplementationRequest,
    Field(discriminator="type"),
]


class PythonImplementationResponse(BaseModel):
    type: Literal["python"]
    code: str
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue]


class JinjaImplementationResponse(BaseModel):
    type: Literal["jinja"]
    template: str
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue]


type ImplementationResponse = Annotated[
    PythonImplementationResponse | JinjaImplementationResponse,
    Field(discriminator="type"),
]
