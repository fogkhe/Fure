import unittest

from fure.core.function import Function
from fure.core.implementations import JinjaImplementation
from fure.core.revision import Revision
from fure.core.runners.jinja.base import BaseJinjaRunnerOptions


class JSONSchemaTests(unittest.TestCase):
    def test_jinja_preserves_nested_output_schemas(self):
        implementation = JinjaImplementation(
            "Hello!", output_schema={"properties": {"value": {"items": True}}}
        )

        self.assertEqual(
            implementation.output_schema,
            {"properties": {"value": {"items": True}}},
        )

    def test_function_without_revision_has_empty_schemas(self):
        function = Function("example")
        self.assertEqual(function.input_schema, {})
        self.assertEqual(function.output_schema, {})

    def test_function_uses_current_revision_schemas(self):
        function = Function("example")
        implementation = JinjaImplementation(
            "{{ name }}", output_schema={"type": "string"}
        )
        revision = Revision(
            implementation,
            BaseJinjaRunnerOptions(timeout=None),
            function,
        )
        function.revision = revision

        self.assertEqual(function.input_schema, implementation.input_schema)
        self.assertEqual(function.output_schema, implementation.output_schema)


if __name__ == "__main__":
    unittest.main()
