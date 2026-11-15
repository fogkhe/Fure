import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from fure.core.implementations import PythonImplementation
from fure.core.runners import (
    BaseJinjaRunnerOptions,
    BasePythonRunnerOptions,
    BaseRunnerOptions,
    InlinePythonRunMeta,
    InlinePythonRunner,
)


class InlinePythonRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.started = asyncio.Event()
        self.state = {"cancelled": False, "finished": False, "returned": False}
        self.implementation = Mock(spec=PythonImplementation)
        self.implementation.execute = AsyncMock(side_effect=self._execute)

    async def _execute(self, input):
        self.started.set()
        try:
            await asyncio.sleep(0.1)
            self.state["returned"] = True
            return "done"
        except asyncio.CancelledError:
            self.state["cancelled"] = True
            raise
        finally:
            self.state["finished"] = True

    async def test_timeout_cancels_function_and_runs_cleanup(self):
        runner = InlinePythonRunner(BasePythonRunnerOptions(timeout=0.01))

        with self.assertRaises(TimeoutError):
            await runner.run(self.implementation, None)

        self.assertEqual(
            self.state,
            {"cancelled": True, "finished": True, "returned": False},
        )

    async def test_none_timeout_is_disabled(self):
        result = await InlinePythonRunner(BasePythonRunnerOptions(timeout=None)).run(
            self.implementation, None
        )

        self.assertEqual(result.output, "done")
        self.assertEqual(result.meta, InlinePythonRunMeta())
        self.assertGreaterEqual(result.duration, 0)
        self.assertFalse(self.state["cancelled"])

    async def test_call_options_override_runner_timeout(self):
        runner = InlinePythonRunner(BasePythonRunnerOptions(timeout=60))

        with self.assertRaises(TimeoutError):
            await runner.run(
                self.implementation, None, BasePythonRunnerOptions(timeout=0.01)
            )

        self.assertTrue(self.state["cancelled"])

    async def test_call_options_can_disable_timeout(self):
        runner = InlinePythonRunner(BasePythonRunnerOptions(timeout=0))

        result = await runner.run(
            self.implementation, None, BasePythonRunnerOptions(timeout=None)
        )

        self.assertEqual(result.output, "done")

    async def test_external_cancellation_propagates(self):
        runner = InlinePythonRunner(BasePythonRunnerOptions(timeout=60))
        task = asyncio.create_task(runner.run(self.implementation, None))
        await self.started.wait()

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertTrue(self.state["cancelled"])
        self.assertTrue(self.state["finished"])

    async def test_function_errors_propagate(self):
        implementation = PythonImplementation(
            """
async def function(input: None) -> None:
    raise ValueError("function failed")
"""
        )
        runner = InlinePythonRunner(BasePythonRunnerOptions(timeout=60))

        with self.assertRaisesRegex(ValueError, "function failed"):
            await runner.run(implementation, None)

    async def test_incompatible_options_are_rejected_before_execution(self):
        runner = InlinePythonRunner(BasePythonRunnerOptions(timeout=None))
        for options in (
            BaseRunnerOptions(timeout=None),
            BaseJinjaRunnerOptions(timeout=None),
        ):
            with self.subTest(options=type(options).__name__):
                with self.assertRaises(TypeError):
                    await InlinePythonRunner(options).run(self.implementation, None)
                with self.assertRaises(TypeError):
                    await runner.run(self.implementation, None, options)

        self.implementation.execute.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
