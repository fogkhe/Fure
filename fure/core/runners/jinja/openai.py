import json
from dataclasses import dataclass
from time import monotonic

from openai import AsyncOpenAI, Omit, omit
from openai.types.shared_params.response_format_json_schema import (
    ResponseFormatJSONSchema,
)

from fure.core.implementations import JinjaImplementation
from fure.core.run import SucceedRunMeta
from fure.core.runners.base import RunResult
from fure.core.runners.jinja.base import BaseJinjaRunner, BaseJinjaRunnerOptions
from fure.core.types import JSONValue


@dataclass(frozen=True, slots=True)
class OpenAIJinjaRunMeta(SucceedRunMeta):
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True, slots=True)
class OpenAIJinjaRunnerOptions(BaseJinjaRunnerOptions):
    api_key: str | None
    base_url: str
    model: str


class OpenAIJinjaRunner(
    BaseJinjaRunner[
        OpenAIJinjaRunnerOptions,
        OpenAIJinjaRunMeta,
    ]
):
    async def run(
        self,
        implementation: JinjaImplementation,
        input: dict[str, JSONValue] | None,
        options: OpenAIJinjaRunnerOptions | None = None,
    ) -> RunResult[OpenAIJinjaRunMeta]:
        options = options if options is not None else self._options

        output_schema = implementation.output_schema
        structured_output = bool(output_schema)

        response_format: ResponseFormatJSONSchema | Omit = omit
        if structured_output:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "output",
                    "schema": dict(output_schema),
                    "strict": True,
                },
            }

        start_time = monotonic()

        prompt = implementation.render(input)

        messages = []
        if structured_output:
            messages.append(
                {"role": "system", "content": "The output must conform to the schema."},
            )
        messages.append(
            {"role": "user", "content": prompt},
        )

        async with AsyncOpenAI(
            api_key=options.api_key if options.api_key is not None else "none",
            base_url=options.base_url,
            timeout=options.timeout,
        ) as client:
            completion = await client.chat.completions.create(
                model=options.model,
                messages=messages,
                response_format=response_format,
            )

        duration = monotonic() - start_time

        if not completion.choices:
            raise RuntimeError(
                "Chat completion returned no choices",
            )
        choice = completion.choices[0]
        if structured_output:
            if choice.message.refusal:
                raise RuntimeError(
                    "Chat completion refused to produce structured output",
                )
            if choice.finish_reason != "stop":
                raise RuntimeError(
                    "Chat completion did not finish the structured output",
                )
        content = choice.message.content
        if content is None:
            raise RuntimeError(
                "Chat completion returned no text content",
            )

        output = content
        if structured_output:
            try:
                output = json.loads(content)
            except json.JSONDecodeError as error:
                raise ValueError(
                    "Chat completion returned invalid JSON",
                ) from error

        usage = completion.usage
        return RunResult(
            output=output,
            meta=OpenAIJinjaRunMeta(
                input_tokens=usage.prompt_tokens if usage is not None else None,
                output_tokens=usage.completion_tokens if usage is not None else None,
                total_tokens=usage.total_tokens if usage is not None else None,
            ),
            duration=duration,
        )
