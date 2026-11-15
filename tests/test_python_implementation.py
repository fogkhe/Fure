import asyncio
import json
import unittest
from types import ModuleType
from unittest.mock import patch

from pydantic import ValidationError

from fure.core.errors import InputValidationError
from fure.core.implementations.python import PythonImplementation


class PythonImplementationTests(unittest.TestCase):
    def test_construction_and_code_access_do_not_execute_module(self):
        state = ModuleType("_fure_test_state")
        state.events = []
        code = """
from _fure_test_state import events
events.append('loaded')
raise RuntimeError('module must not run on construction')
"""
        with patch.dict("sys.modules", {"_fure_test_state": state}):
            implementation = PythonImplementation(code)

            self.assertEqual(implementation.code, code)
            self.assertEqual(state.events, [])

    def test_first_use_prepares_module_once_and_caches_schemas(self):
        state = ModuleType("_fure_test_state")
        state.events = []
        code = """
from _fure_test_state import events
events.append('loaded')

async def function(input: None) -> int:
    events.append('called')
    return events.count('called')
"""
        with patch.dict("sys.modules", {"_fure_test_state": state}):
            implementation = PythonImplementation(code)
            self.assertEqual(state.events, [])

            input_schema = implementation.input_schema
            input_schema["type"] = "string"
            self.assertEqual(implementation.input_schema, {"type": "null"})
            self.assertEqual(implementation.output_schema, {"type": "integer"})
            self.assertEqual(state.events, ["loaded"])

            self.assertEqual(asyncio.run(implementation.execute(None)), 1)
            self.assertEqual(asyncio.run(implementation.execute(None)), 2)
            self.assertEqual(state.events, ["loaded", "called", "called"])

    def test_restoring_domain_objects_and_reading_schemas_does_not_execute_code(self):
        from fure.core.function import Function
        from fure.core.revision import Revision
        from fure.core.run import Run
        from fure.core.runners import BasePythonRunnerOptions

        code = "raise RuntimeError('code must not run while reading a revision')"
        input_schema = {"type": "object", "properties": {"value": {"type": "integer"}}}
        output_schema = {"type": "string"}
        implementation = PythonImplementation.restore(
            code, input_schema=input_schema, output_schema=output_schema
        )
        function = Function("example")
        revision = Revision(
            implementation, BasePythonRunnerOptions(timeout=None), function
        )
        function.revision = revision
        run = Run(revision, None)

        input_schema["properties"]["value"]["type"] = "string"
        output_schema["type"] = "integer"
        exposed_schema = function.input_schema
        exposed_schema["properties"]["value"]["type"] = "boolean"

        self.assertEqual(run.revision.implementation.code, code)
        self.assertEqual(
            function.input_schema,
            {"type": "object", "properties": {"value": {"type": "integer"}}},
        )
        self.assertEqual(function.output_schema, {"type": "string"})

    def test_restored_empty_schemas_are_preserved_without_preparation(self):
        implementation = PythonImplementation.restore(
            "raise RuntimeError('not executed')", input_schema={}, output_schema={}
        )

        self.assertEqual(implementation.input_schema, {})
        self.assertEqual(implementation.output_schema, {})

    def test_restored_implementation_prepares_on_execution_and_validates_annotations(
        self,
    ):
        state = ModuleType("_fure_test_state")
        state.events = []
        code = """
from _fure_test_state import events
from typing import Annotated
from pydantic import BaseModel, Field

events.append('loaded')

class Input(BaseModel):
    value: Annotated[int, Field(ge=1)]

async def function(input: Input) -> int:
    return input.value
"""
        with patch.dict("sys.modules", {"_fure_test_state": state}):
            original = PythonImplementation(code)
            input_schema = original.input_schema
            output_schema = original.output_schema
            state.events.clear()

            restored = PythonImplementation.restore(
                original.code, input_schema=input_schema, output_schema=output_schema
            )
            self.assertEqual(restored.input_schema, input_schema)
            self.assertEqual(restored.output_schema, output_schema)
            self.assertEqual(state.events, [])

            with self.assertRaises(InputValidationError):
                asyncio.run(restored.execute({"value": 0}))
            self.assertEqual(asyncio.run(restored.execute({"value": 3})), 3)
            self.assertEqual(state.events, ["loaded"])
            self.assertEqual(restored.input_schema, input_schema)
            self.assertEqual(restored.output_schema, output_schema)

    def test_syntax_and_module_errors_are_reported_when_code_is_used(self):
        cases = (
            ("async def function(: pass", ValueError, "valid Python syntax"),
            ("raise RuntimeError('failed')", RuntimeError, "execution raised an error"),
        )
        for code, error_type, message in cases:
            with self.subTest(code=code):
                implementation = PythonImplementation(code)
                with self.assertRaisesRegex(error_type, message):
                    asyncio.run(implementation.execute(None))

    def test_schemas_and_validation_follow_function_annotations(self):
        implementation = PythonImplementation(
            """
from typing import Annotated
from pydantic import BaseModel, Field, NonNegativeFloat

Input = None
Output = str

class CanBeCalledAnything(BaseModel):
    x: float
    y: Annotated[float, Field(ge=1)]

async def function(input: CanBeCalledAnything) -> NonNegativeFloat:
    return input.x + input.y
"""
        )

        self.assertEqual(implementation.input_schema["title"], "CanBeCalledAnything")
        self.assertEqual(implementation.input_schema["properties"]["y"]["minimum"], 1)
        self.assertEqual(implementation.output_schema, {"minimum": 0, "type": "number"})
        self.assertEqual(asyncio.run(implementation.execute({"x": 2, "y": 3})), 5)

        with self.assertRaises(InputValidationError):
            asyncio.run(implementation.execute({"x": 2, "y": 0}))
        with self.assertRaises(ValidationError):
            asyncio.run(implementation.execute({"x": -5, "y": 1}))

    def test_forward_references_and_annotated_metadata(self):
        for future_import in ("", "from __future__ import annotations"):
            with self.subTest(future_import=future_import):
                implementation = PythonImplementation(
                    future_import
                    + """
from typing import Annotated
from pydantic import BaseModel, Field

async def function(
    input: "Annotated[Payload, Field(description='Input data')]",
) -> "Annotated[int, Field(ge=1)]":
    return input.value

class Payload(BaseModel):
    value: int
"""
                )

                self.assertEqual(
                    implementation.input_schema["description"], "Input data"
                )
                self.assertEqual(
                    asyncio.run(implementation.execute({"value": 4})),
                    4,
                )
                self.assertEqual(implementation.output_schema["minimum"], 1)
                with self.assertRaises(ValidationError):
                    asyncio.run(implementation.execute({"value": 0}))

    def test_explicit_none_annotations(self):
        implementation = PythonImplementation(
            "async def function(input: None) -> None: pass"
        )

        self.assertEqual(implementation.input_schema, {"type": "null"})
        self.assertEqual(implementation.output_schema, {"type": "null"})
        self.assertIsNone(asyncio.run(implementation.execute(None)))

    def test_input_aliases_preserve_annotations_and_validation(self):
        aliases = (
            "type InputData = Payload",
            "type InputData = Annotated[Payload, Field(description='Input data')]",
            (
                "type Inner = Annotated[Payload, Field(description='Input data')]\n"
                "type Middle = Inner\n"
                "type InputData = Annotated[Middle, AfterValidator(increment)]"
            ),
        )
        for alias in aliases:
            with self.subTest(alias=alias):
                implementation = PythonImplementation(
                    """
from typing import Annotated
from pydantic import AfterValidator, BaseModel, Field

class Payload(BaseModel):
    value: Annotated[int, Field(ge=1)]

def increment(input: Payload) -> Payload:
    input.value += 1
    return input

"""
                    + alias
                    + """

type Output = int

async def function(input: InputData) -> Output:
    return input.value
"""
                )

                expected = 5 if "AfterValidator(increment)" in alias else 4
                self.assertEqual(
                    asyncio.run(implementation.execute({"value": 4})), expected
                )
                with self.assertRaises(InputValidationError):
                    asyncio.run(implementation.execute({"value": 0}))
                if "Input data" in alias:
                    self.assertIn("Input data", json.dumps(implementation.input_schema))
                self.assertEqual(implementation.output_schema["type"], "integer")

    def test_none_alias(self):
        implementation = PythonImplementation(
            """
type NoInput = None

async def function(input: NoInput) -> None:
    pass
"""
        )

        self.assertEqual(implementation.input_schema["type"], "null")
        self.assertIsNone(asyncio.run(implementation.execute(None)))

    def test_invalid_input_aliases(self):
        aliases = (
            ("type InputData = int", "must be a subclass"),
            ("type InputData = InputData", "must be a subclass"),
            ("type InputData = Other\ntype Other = InputData", "must be a subclass"),
            ("type InputData = Missing", "must be resolvable"),
        )
        for alias, message in aliases:
            with self.subTest(alias=alias), self.assertRaisesRegex(TypeError, message):
                implementation = PythonImplementation(
                    alias + "\nasync def function(input: InputData) -> None: pass"
                )
                _ = implementation.input_schema

    def test_model_return_annotation(self):
        implementation = PythonImplementation(
            """
from pydantic import BaseModel

class Result(BaseModel):
    value: int

async def function(input: None) -> Result:
    return Result(value=5)
"""
        )

        self.assertEqual(asyncio.run(implementation.execute(None)), {"value": 5})

    def test_keyword_only_input_is_passed_by_name(self):
        implementation = PythonImplementation(
            """
from pydantic import BaseModel

class Input(BaseModel):
    value: int

async def function(offset: int = 2, *, input: Input) -> int:
    return offset + input.value
"""
        )

        self.assertEqual(asyncio.run(implementation.execute({"value": 3})), 5)

    def test_output_is_json_serializable_for_scalars_and_nested_models(self):
        definitions = """
from datetime import datetime
from pydantic import BaseModel

class Result(BaseModel):
    value: datetime
"""
        cases = (
            ("datetime", "datetime(2026, 1, 1)", "2026-01-01T00:00:00"),
            (
                "Result",
                "Result(value=datetime(2026, 1, 1))",
                {"value": "2026-01-01T00:00:00"},
            ),
            (
                "list[Result]",
                "[Result(value=datetime(2026, 1, 1))]",
                [{"value": "2026-01-01T00:00:00"}],
            ),
        )
        for annotation, expression, expected in cases:
            with self.subTest(annotation=annotation):
                implementation = PythonImplementation(
                    definitions
                    + f"\nasync def function(input: None) -> {annotation}:\n"
                    + f"    return {expression}\n"
                )

                result = asyncio.run(implementation.execute(None))

                self.assertEqual(result, expected)
                self.assertEqual(json.loads(json.dumps(result)), expected)

    def test_output_schema_matches_serialized_representation(self):
        implementation = PythonImplementation(
            """
from typing import Annotated
from pydantic import PlainSerializer

async def function(input: None) -> Annotated[
    int, PlainSerializer(lambda value: str(value), return_type=str)
]:
    return 5
"""
        )

        self.assertEqual(implementation.output_schema, {"type": "string"})
        self.assertEqual(asyncio.run(implementation.execute(None)), "5")

    def test_pydantic_boolean_subschemas_are_preserved(self):
        implementation = PythonImplementation(
            """
from typing import Any
from pydantic import BaseModel, ConfigDict

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
    values: dict[str, Any]
    enabled: bool = False

async def function(input: Input) -> dict[str, Any]:
    return input.values
"""
        )

        self.assertIs(implementation.input_schema["additionalProperties"], False)
        properties = implementation.input_schema["properties"]
        self.assertIs(properties["values"]["additionalProperties"], True)
        self.assertIs(properties["enabled"]["default"], False)
        self.assertIs(implementation.output_schema["additionalProperties"], True)

    def test_invalid_function_contracts(self):
        cases = (
            ("def function(input: None) -> None: pass", "coroutine function"),
            (
                "async def function(input: None, other) -> None: pass",
                "bindable",
            ),
            ("async def function(input: None, /) -> None: pass", "bindable"),
            (
                "async def function(**kwargs: None) -> None: pass",
                "declare an 'input' parameter",
            ),
            (
                "async def function(**input: None) -> None: pass",
                "declare an 'input' parameter",
            ),
            (
                "Input = None\nasync def function(input) -> None: pass",
                "must have a type annotation",
            ),
            (
                "Output = str\nasync def function(input: None): pass",
                "must have a return type annotation",
            ),
            (
                "async def function(input: 'Missing') -> None: pass",
                "must be resolvable",
            ),
            (
                "async def function(input: None) -> 'Missing': pass",
                "must be resolvable",
            ),
            (
                "async def function(input: int) -> None: pass",
                "must be a subclass of 'BaseModel' or 'None'",
            ),
            (
                (
                    "class Unsupported: pass\n"
                    "async def function(input: None) -> Unsupported: pass"
                ),
                "return annotation must be a JSON serializable type",
            ),
            (
                (
                    "from typing import Callable\n"
                    "async def function(input: None) -> Callable[[], None]: pass"
                ),
                "return annotation must be a JSON serializable type",
            ),
        )
        for code, message in cases:
            with self.subTest(code=code), self.assertRaisesRegex(TypeError, message):
                implementation = PythonImplementation(code)
                _ = implementation.input_schema


if __name__ == "__main__":
    unittest.main()
