import inspect
from annotationlib import Format
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Annotated, Self, TypeAliasType, get_args, get_origin, get_type_hints

from pydantic import (
    BaseModel,
    PydanticUserError,
    TypeAdapter,
)

from fure.core.implementations.base import BaseImplementation
from fure.core.types import JSONSchema, JSONValue


@dataclass
class _InspectResult:
    input_adapter: TypeAdapter[BaseModel | None]
    output_adapter: TypeAdapter[BaseModel | JSONValue]
    function: Callable[..., Awaitable[BaseModel | JSONValue]]
    input_schema: JSONSchema
    output_schema: JSONSchema


class PythonImplementation(BaseImplementation):
    __slots__ = (
        "_code",
        "_input_schema",
        "_inspect_result",
        "_output_schema",
    )

    def __init__(
        self,
        code: str,
    ) -> None:
        self._code = code
        self._inspect_result: _InspectResult | None = None
        self._input_schema: JSONSchema | None = None
        self._output_schema: JSONSchema | None = None

    @classmethod
    def restore(
        cls,
        code: str,
        *,
        input_schema: JSONSchema,
        output_schema: JSONSchema,
    ) -> Self:
        implementation = cls.__new__(cls)
        implementation._code = code
        implementation._inspect_result = None
        implementation._input_schema = deepcopy(input_schema)
        implementation._output_schema = deepcopy(output_schema)
        return implementation

    @property
    def code(self) -> str:
        return self._code

    @property
    def input_schema(self) -> JSONSchema:
        schema = self._input_schema
        if schema is None:
            schema = self._prepare().input_schema
        return deepcopy(schema)

    @property
    def output_schema(self) -> JSONSchema:
        schema = self._output_schema
        if schema is None:
            schema = self._prepare().output_schema
        return deepcopy(schema)

    async def execute(self, input: dict[str, JSONValue] | None) -> JSONValue:
        inspect_result = self._prepare()
        validated_input = inspect_result.input_adapter.validate_python(input)

        output = await inspect_result.function(input=validated_input)

        validated_output = inspect_result.output_adapter.validate_python(output)
        return inspect_result.output_adapter.dump_python(validated_output, mode="json")

    def _prepare(self) -> _InspectResult:
        if self._inspect_result is None:
            self._inspect_result = self._inspect(self._code)
        return self._inspect_result

    @staticmethod
    def _inspect(code: str) -> _InspectResult:
        try:
            compiled_code = compile(
                source=code,
                filename="<fure>",
                mode="exec",
            )
        except SyntaxError as error:
            raise ValueError(
                "'code' must use valid Python syntax",
            ) from error

        namespace = {}
        try:
            exec(  # noqa: S102
                compiled_code,
                globals=namespace,
                locals=namespace,
            )
        except Exception as error:
            raise RuntimeError(
                "'code' execution raised an error",
            ) from error

        function = namespace.get("function")

        if not inspect.iscoroutinefunction(function):
            raise TypeError(
                "'function' must be a coroutine function",
            )
        signature = inspect.signature(function, annotation_format=Format.STRING)
        try:
            signature.bind(input=...)
        except TypeError as error:
            raise TypeError(
                "'function' must be bindable to (input=...)",
            ) from error

        input_parameter = signature.parameters.get("input")
        if input_parameter is None or input_parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            raise TypeError("'function' must declare an 'input' parameter")
        if input_parameter.annotation is inspect.Parameter.empty:
            raise TypeError("'function.input' must have a type annotation")
        if signature.return_annotation is inspect.Signature.empty:
            raise TypeError("'function' must have a return type annotation")

        try:
            annotations = get_type_hints(
                function,
                globalns=namespace,
                localns=namespace,
                include_extras=True,
            )
        except (NameError, TypeError) as error:
            raise TypeError(
                "'function' type annotations must be resolvable",
            ) from error

        input_type = annotations["input"]
        output_type = annotations["return"]

        input_class = input_type
        seen_aliases: set[TypeAliasType] = set()
        try:
            while True:
                if get_origin(input_class) is Annotated:
                    input_class = get_args(input_class)[0]
                elif isinstance(input_class, TypeAliasType):
                    if input_class in seen_aliases:
                        break
                    seen_aliases.add(input_class)
                    input_class = input_class.__value__
                else:
                    break
        except (NameError, TypeError) as error:
            raise TypeError(
                "'function' type annotations must be resolvable",
            ) from error

        if (
            input_class is not None
            and input_class is not type(None)
            and not (
                isinstance(input_class, type) and issubclass(input_class, BaseModel)
            )
        ):
            raise TypeError(
                "'function.input' annotation must be a subclass of 'BaseModel' or 'None'",
            )
        try:
            input_adapter = TypeAdapter(input_type)
            input_schema = input_adapter.json_schema()
        except PydanticUserError as error:
            raise TypeError(
                "'function.input' annotation must be a JSON serializable type",
            ) from error

        try:
            output_adapter = TypeAdapter(output_type)
            output_schema = output_adapter.json_schema(mode="serialization")
        except PydanticUserError as error:
            raise TypeError(
                "'function' return annotation must be a JSON serializable type",
            ) from error

        return _InspectResult(
            input_adapter=input_adapter,
            output_adapter=output_adapter,
            function=function,
            input_schema=input_schema,
            output_schema=output_schema,
        )
