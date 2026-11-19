import unittest

from jinja2 import TemplateSyntaxError, UndefinedError
from jinja2.sandbox import SecurityError

from fure.core.implementations import JinjaImplementation


class JinjaImplementationTests(unittest.TestCase):
    def test_schema_and_render_match_example(self):
        template = "Hello, {{ name }}!"
        implementation = JinjaImplementation(template)

        self.assertEqual(implementation.template, template)
        self.assertEqual(
            implementation.input_schema,
            {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {}},
            },
        )
        self.assertEqual(implementation.render({"name": "world"}), "Hello, world!")
        self.assertEqual(implementation.output_schema, {})

    def test_legacy_revision_keeps_vars_as_user_input(self):
        implementation = JinjaImplementation.restore(
            "{{ vars }}",
            input_schema={
                "type": "object",
                "required": ["vars"],
                "properties": {"vars": {}},
            },
            output_schema={},
        )
        self.assertEqual(
            implementation.render({"vars": "legacy"}, variables={"key": "shared"}),
            "legacy",
        )

    def test_variable_names_are_unique_and_sorted(self):
        implementation = JinjaImplementation("{{ z }} {{ a | upper }} {{ z }}")

        self.assertEqual(implementation.input_schema["required"], ["a", "z"])
        self.assertEqual(
            implementation.render({"z": "last", "a": "first"}), "last FIRST last"
        )

    def test_local_variables_and_builtins_are_excluded(self):
        implementation = JinjaImplementation(
            """
{% set punctuation = '!' %}
{% macro greet(person) %}{{ person }}{{ punctuation }}{% endmacro %}
{% for character in name %}{{ loop.index }}: {{ greet(character) }}{% endfor %}
{% for index in range(2) %}{{ index }}{% endfor %}
"""
        )

        self.assertEqual(implementation.input_schema["required"], ["name"])
        self.assertIn("1: A!", implementation.render({"name": "AB"}))

    def test_comments_and_raw_blocks_do_not_add_variables(self):
        implementation = JinjaImplementation(
            "{# {{ ignored }} #}{% raw %}{{ literal }}{% endraw %}{{ name }}"
        )

        self.assertEqual(implementation.input_schema["required"], ["name"])
        self.assertEqual(implementation.render({"name": "world"}), "{{ literal }}world")

    def test_template_without_variables_accepts_none(self):
        implementation = JinjaImplementation("Hello!")

        self.assertEqual(
            implementation.input_schema,
            {"type": "object", "required": [], "properties": {}},
        )
        self.assertEqual(implementation.render(None), "Hello!")

    def test_missing_variables_raise(self):
        implementation = JinjaImplementation("Hello, {{ name }}!")

        for input_value in ({}, None):
            with self.subTest(input=input_value), self.assertRaises(UndefinedError):
                implementation.render(input_value)

    def test_invalid_templates_raise_at_construction(self):
        for template in ("{{ name", "{{ name | nonexistent_filter }}"):
            with self.subTest(template=template):
                with self.assertRaisesRegex(ValueError, "valid Jinja syntax") as caught:
                    JinjaImplementation(template)
                self.assertIsInstance(caught.exception.__cause__, TemplateSyntaxError)

    def test_sandbox_blocks_unsafe_attribute_access(self):
        implementation = JinjaImplementation("{{ name.__class__ }}")

        with self.assertRaises(SecurityError):
            implementation.render({"name": "world"})

    def test_sandbox_prevents_input_mutation(self):
        implementation = JinjaImplementation("{{ data.update({'value': 'changed'}) }}")
        data = {"value": "original"}

        with self.assertRaises(SecurityError):
            implementation.render({"data": data})
        self.assertEqual(data, {"value": "original"})

    def test_input_schema_changes_do_not_affect_implementation(self):
        implementation = JinjaImplementation("{{ name }}")
        schema = implementation.input_schema
        schema["required"].clear()
        schema["properties"]["name"]["type"] = "integer"

        self.assertEqual(implementation.input_schema["required"], ["name"])
        self.assertEqual(implementation.input_schema["properties"]["name"], {})

    def test_default_output_schemas_are_independent(self):
        first = JinjaImplementation("first")
        second = JinjaImplementation("second")
        schema = first.output_schema
        schema["type"] = "string"

        self.assertEqual(first.output_schema, {})
        self.assertEqual(second.output_schema, {})

    def test_custom_output_schema_is_preserved(self):
        schema = {"type": "string", "maxLength": 100}

        self.assertEqual(JinjaImplementation("hello", schema).output_schema, schema)


if __name__ == "__main__":
    unittest.main()
