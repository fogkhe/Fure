import unittest
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID

from fure.core.function import Function
from fure.core.implementations import JinjaImplementation, PythonImplementation
from fure.core.revision import Revision
from fure.core.run import CancelRunMeta, FailRunMeta, Run, RunStatus, SucceedRunMeta
from fure.core.runners import BasePythonRunnerOptions


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.id = UUID("01900000-0000-7000-8000-000000000001")
        self.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        self.updated_at = self.created_at + timedelta(days=1)
        self.function = Function("example")
        self.implementation = PythonImplementation.restore(
            "raise RuntimeError('must not run during restoration')",
            input_schema={"type": "null"},
            output_schema={"type": "string"},
        )
        self.options = BasePythonRunnerOptions(timeout=None)
        self.revision = Revision(self.implementation, self.options, self.function)

    def test_function_restores_identity_flags_dates_and_revision_without_constructor(
        self,
    ):
        deleted_at = self.updated_at + timedelta(days=1)
        with patch.object(
            Function, "__init__", side_effect=AssertionError("constructor called")
        ):
            function = Function.restore(
                id=self.id,
                name="stored_function",
                description="Stored description",
                revision=self.revision,
                enabled=False,
                created_at=self.created_at,
                updated_at=self.updated_at,
                deleted_at=deleted_at,
            )

        self.assertEqual(function.id, self.id)
        self.assertEqual(function.name, "stored_function")
        self.assertEqual(function.description, "Stored description")
        self.assertIs(function.revision, self.revision)
        self.assertFalse(function.enabled)
        self.assertTrue(function.deleted)
        self.assertFalse(function.runnable)
        self.assertEqual(function.created_at, self.created_at)
        self.assertEqual(function.updated_at, self.updated_at)
        self.assertEqual(function.deleted_at, deleted_at)
        self.assertEqual(function.input_schema, {"type": "null"})
        self.assertEqual(function.output_schema, {"type": "string"})

    def test_revision_restores_owner_and_configuration_without_constructor(self):
        with patch.object(
            Revision, "__init__", side_effect=AssertionError("constructor called")
        ):
            revision = Revision.restore(
                id=self.id,
                implementation=self.implementation,
                runner_options=self.options,
                function=self.function,
                created_at=self.created_at,
            )

        self.assertEqual(revision.id, self.id)
        self.assertIs(revision.function, self.function)
        self.assertIs(revision.implementation, self.implementation)
        self.assertIs(revision.runner_options, self.options)
        self.assertEqual(revision.created_at, self.created_at)
        self.assertIs(self.revision.function, self.function)
        self.assertIsNone(self.function.revision)

    def test_run_restores_all_statuses_without_replaying_transitions(self):
        for status, meta in (
            (RunStatus.PENDING, None),
            (RunStatus.RUNNING, None),
            (RunStatus.SUCCEEDED, SucceedRunMeta()),
            (RunStatus.FAILED, FailRunMeta()),
            (RunStatus.CANCELLED, CancelRunMeta()),
        ):
            with self.subTest(status=status):
                started_at = None if status is RunStatus.PENDING else self.created_at
                finished_at = (
                    None
                    if status in (RunStatus.PENDING, RunStatus.RUNNING)
                    else self.updated_at
                )
                duration = None if finished_at is None else 1.25
                output = "done" if status is RunStatus.SUCCEEDED else None
                with patch.object(
                    Run, "__init__", side_effect=AssertionError("constructor called")
                ):
                    run = Run.restore(
                        id=self.id,
                        revision=self.revision,
                        input=None,
                        status=status,
                        output=output,
                        meta=meta,
                        duration=duration,
                        started_at=started_at,
                        finished_at=finished_at,
                        created_at=self.created_at,
                        updated_at=self.updated_at,
                    )

                self.assertEqual(run.id, self.id)
                self.assertIs(run.revision, self.revision)
                self.assertIsNone(run.input)
                self.assertIs(run.status, status)
                self.assertEqual(run.output, output)
                self.assertEqual(run.meta, meta)
                self.assertEqual(run.duration, duration)
                self.assertEqual(run.started_at, started_at)
                self.assertEqual(run.finished_at, finished_at)
                self.assertEqual(run.created_at, self.created_at)
                self.assertEqual(run.updated_at, self.updated_at)

    def test_run_restoration_keeps_defensive_copies_of_data_and_metadata(self):
        @dataclass(frozen=True, slots=True)
        class DetailedFailRunMeta(FailRunMeta):
            errors: list[str]

        input = {"values": [1]}
        output = {"partial": [2]}
        meta = DetailedFailRunMeta(errors=["failed"])
        run = Run.restore(
            id=self.id,
            revision=self.revision,
            input=input,
            status=RunStatus.FAILED,
            output=output,
            meta=meta,
            duration=1,
            started_at=self.created_at,
            finished_at=self.updated_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

        input["values"].append(3)
        output["partial"].clear()
        meta.errors.clear()
        run.input["values"].clear()
        run.output["partial"].clear()
        run.meta.errors.clear()

        self.assertEqual(run.input, {"values": [1]})
        self.assertEqual(run.output, {"partial": [2]})
        self.assertEqual(run.meta, DetailedFailRunMeta(errors=["failed"]))

    def test_restored_jinja_compiles_only_on_first_render_and_keeps_saved_schemas(self):
        template = "Hello, {{ name }}!"
        original = JinjaImplementation(template, output_schema={"type": "string"})
        input_schema = original.input_schema
        output_schema = original.output_schema
        with (
            patch.object(
                JinjaImplementation,
                "__init__",
                side_effect=AssertionError("constructor called"),
            ),
            patch.object(
                JinjaImplementation, "_compile", wraps=JinjaImplementation._compile
            ) as compile_template,
        ):
            restored = JinjaImplementation.restore(
                template, input_schema=input_schema, output_schema=output_schema
            )
            input_schema["properties"]["name"]["type"] = "integer"
            output_schema["type"] = "number"

            self.assertEqual(restored.template, template)
            self.assertEqual(restored.input_schema, original.input_schema)
            self.assertEqual(restored.output_schema, original.output_schema)
            compile_template.assert_not_called()

            self.assertEqual(restored.render({"name": "world"}), "Hello, world!")
            self.assertEqual(restored.render({"name": "again"}), "Hello, again!")
            compile_template.assert_called_once_with(template)
            self.assertEqual(restored.input_schema, original.input_schema)
            self.assertEqual(restored.output_schema, original.output_schema)

    def test_invalid_saved_template_can_be_read_but_fails_when_rendered(self):
        restored = JinjaImplementation.restore(
            "{{ name", input_schema={}, output_schema={}
        )

        self.assertEqual(restored.template, "{{ name")
        self.assertEqual(restored.input_schema, {})
        self.assertEqual(restored.output_schema, {})
        with self.assertRaisesRegex(ValueError, "valid Jinja syntax"):
            restored.render(None)

    def test_python_restoration_bypasses_constructor_as_well(self):
        with patch.object(
            PythonImplementation,
            "__init__",
            side_effect=AssertionError("constructor called"),
        ):
            restored = PythonImplementation.restore(
                self.implementation.code,
                input_schema={"type": "null"},
                output_schema={"type": "string"},
            )

        self.assertEqual(restored.code, self.implementation.code)
        self.assertEqual(restored.input_schema, {"type": "null"})
        self.assertEqual(restored.output_schema, {"type": "string"})


if __name__ == "__main__":
    unittest.main()
