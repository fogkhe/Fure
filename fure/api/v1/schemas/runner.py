from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr

from fure.api.v1.schemas.common import RequestSchema

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


type RunnerOptionsResponse = Annotated[
    InlinePythonRunnerOptionsResponse | OpenAIJinjaRunnerOptionsResponse,
    Field(discriminator="type"),
]
