from copy import deepcopy
from dataclasses import dataclass
from typing import Self

from jinja2 import StrictUndefined, Template, TemplateSyntaxError, meta
from jinja2.sandbox import ImmutableSandboxedEnvironment

from fure.core.implementations.base import BaseImplementation
from fure.core.types import JSONSchema, JSONValue


@dataclass
class _CompileResult:
    compiled_template: Template
    input_schema: JSONSchema


class JinjaImplementation(BaseImplementation):
    __slots__ = (
        "_compiled_template",
        "_input_schema",
        "_output_schema",
        "_template",
    )

    def __init__(
        self,
        template: str,
        output_schema: JSONSchema | None = None,
    ) -> None:
        self._template = template
        self._output_schema = (
            deepcopy(output_schema) if output_schema is not None else {}
        )

        compile_result = self._compile(self._template)
        self._compiled_template: Template | None = compile_result.compiled_template
        self._input_schema = compile_result.input_schema

    @classmethod
    def restore(
        cls,
        template: str,
        *,
        input_schema: JSONSchema,
        output_schema: JSONSchema,
    ) -> Self:
        implementation = cls.__new__(cls)
        implementation._template = template
        implementation._input_schema = deepcopy(input_schema)
        implementation._output_schema = deepcopy(output_schema)
        implementation._compiled_template = None
        return implementation

    @property
    def template(self) -> str:
        return self._template

    @property
    def input_schema(self) -> JSONSchema:
        return deepcopy(self._input_schema)

    @property
    def output_schema(self) -> JSONSchema:
        return deepcopy(self._output_schema)

    @property
    def accepts_vars(self) -> bool:
        # Older versions could declare a user input named vars.
        return "vars" not in self._input_schema.get("required", [])

    def render(
        self,
        input: dict[str, JSONValue] | None,
        *,
        variables: dict[str, JSONValue] | None = None,
    ) -> str:
        if self._compiled_template is None:
            self._compiled_template = self._compile(self._template).compiled_template
        context = dict(input or {})
        if self.accepts_vars:
            context["vars"] = variables if variables is not None else {}
        return self._compiled_template.render(context)

    @staticmethod
    def _compile(template: str) -> _CompileResult:
        environment = ImmutableSandboxedEnvironment(
            undefined=StrictUndefined,
        )
        environment.globals["vars"] = StrictUndefined(name="vars")

        try:
            parsed_template = environment.parse(template)
            variables = sorted(meta.find_undeclared_variables(parsed_template))
            compiled_template = environment.from_string(parsed_template)
        except TemplateSyntaxError as error:
            raise ValueError(
                "'template' must use valid Jinja syntax",
            ) from error

        input_schema = {
            "type": "object",
            "required": variables,
            "properties": {name: {} for name in variables},
        }

        return _CompileResult(
            compiled_template=compiled_template,
            input_schema=input_schema,
        )
