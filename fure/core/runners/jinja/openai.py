import json
from dataclasses import dataclass
from time import monotonic

from jsonschema.validators import validator_for
from openai import AsyncOpenAI, Omit, omit
from openai.types.shared_params.response_format_json_schema import (
    ResponseFormatJSONSchema,
)
from referencing import Registry

from fure.core.implementations import JinjaImplementation
from fure.core.run import SucceedRunMeta
from fure.core.runners.base import RunResult
from fure.core.runners.jinja.base import BaseJinjaRunner, BaseJinjaRunnerOptions
from fure.core.types import JSONValue
from fure.utils.json_extraction import extract_json, parse_json


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
    structured_outputs: bool = True
    reasoning_end_tags: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "reasoning_end_tags", tuple(self.reasoning_end_tags))
        if any(not tag.strip() for tag in self.reasoning_end_tags):
            raise ValueError("Reasoning end tags cannot be empty")


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
        json_output = bool(output_schema)
        structured_output = json_output and options.structured_outputs

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
        if json_output:
            instruction = "The output must conform to the schema."
            if not structured_output:
                instruction = (
                    "Return exactly one JSON value matching this JSON Schema. "
                    "Do not include explanations or Markdown.\n"
                    + json.dumps(output_schema, ensure_ascii=False)
                )
            messages.append(
                {"role": "system", "content": instruction},
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

        if not completion.choices:
            raise RuntimeError(
                "Chat completion returned no choices",
            )
        choice = completion.choices[0]
        if json_output:
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
        if json_output:
            try:
                output = (
                    parse_json(content)
                    if structured_output
                    else extract_json(content, options.reasoning_end_tags)
                )
            except ValueError as error:
                raise ValueError(
                    "Chat completion returned invalid JSON or multiple JSON values",
                ) from error
            validator_type = validator_for(output_schema)
            validator_type.check_schema(output_schema)
            validator_type(output_schema, registry=Registry()).validate(output)

        usage = completion.usage
        return RunResult(
            output=output,
            meta=OpenAIJinjaRunMeta(
                input_tokens=usage.prompt_tokens if usage is not None else None,
                output_tokens=usage.completion_tokens if usage is not None else None,
                total_tokens=usage.total_tokens if usage is not None else None,
            ),
            duration=monotonic() - start_time,
        )
