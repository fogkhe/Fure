import unittest

from fure.core.function import Function
from fure.core.implementations import JinjaImplementation, PythonImplementation
from fure.core.revision import Revision
from fure.core.runners import BaseRunnerOptions, OpenAIJinjaRunnerOptions
from fure.core.runners.jinja.base import BaseJinjaRunnerOptions
from fure.core.runners.python.base import BasePythonRunnerOptions


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.function = Function("example")
        self.python = PythonImplementation(
            "async def function(input: None) -> str:\n    return 'hello'\n"
        )
        self.jinja = JinjaImplementation("Hello!")
        self.python_options = BasePythonRunnerOptions(timeout=None)
        self.jinja_options = BaseJinjaRunnerOptions(timeout=None)

    def test_accepts_matching_implementation_and_options(self):
        for implementation, options in (
            (self.python, self.python_options),
            (self.jinja, self.jinja_options),
            (
                self.jinja,
                OpenAIJinjaRunnerOptions(
                    timeout=10,
                    api_key=None,
                    base_url="http://localhost:11434/v1",
                    model="test-model",
                ),
            ),
        ):
            with self.subTest(options=type(options).__name__):
                revision = Revision(implementation, options, self.function)

                self.assertIs(revision.implementation, implementation)
                self.assertIs(revision.runner_options, options)

    def test_rejects_options_for_another_implementation(self):
        for implementation, options in (
            (self.python, self.jinja_options),
            (self.jinja, self.python_options),
        ):
            with self.subTest(implementation=type(implementation).__name__):
                with self.assertRaises(TypeError) as error:
                    Revision(implementation, options, self.function)

                self.assertIn(type(implementation).__name__, str(error.exception))
                self.assertIn(type(options).__name__, str(error.exception))

    def test_rejects_options_without_implementation_family(self):
        for implementation in (self.python, self.jinja):
            with (
                self.subTest(implementation=type(implementation).__name__),
                self.assertRaises(TypeError),
            ):
                Revision(implementation, BaseRunnerOptions(timeout=None), self.function)

    def test_accepts_implementation_and_options_subclasses(self):
        class CustomPythonImplementation(PythonImplementation):
            pass

        class CustomPythonRunnerOptions(BasePythonRunnerOptions):
            pass

        implementation = CustomPythonImplementation(
            "async def function(input: None) -> str:\n    return 'hello'\n"
        )
        options = CustomPythonRunnerOptions(timeout=None)

        revision = Revision(implementation, options, self.function)

        self.assertIs(revision.implementation, implementation)
        self.assertIs(revision.runner_options, options)


if __name__ == "__main__":
    unittest.main()
