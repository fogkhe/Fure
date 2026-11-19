import asyncio
from dataclasses import dataclass
from time import monotonic

from fure.core.implementations import PythonImplementation
from fure.core.run import SucceedRunMeta
from fure.core.runners.base import RunResult
from fure.core.runners.python.base import BasePythonRunner, BasePythonRunnerOptions
from fure.core.types import JSONValue


@dataclass(frozen=True, slots=True)
class InlinePythonRunnerOptions(BasePythonRunnerOptions): ...


@dataclass(frozen=True, slots=True)
class InlinePythonRunMeta(SucceedRunMeta): ...


class InlinePythonRunner(
    BasePythonRunner[
        InlinePythonRunnerOptions,
        InlinePythonRunMeta,
    ]
):
    async def run(
        self,
        implementation: PythonImplementation,
        input: dict[str, JSONValue] | None,
        options: BasePythonRunnerOptions | None = None,
        *,
        variables: dict[str, JSONValue] | None = None,
    ) -> RunResult[InlinePythonRunMeta]:
        options = options if options is not None else self._options
        if not isinstance(options, BasePythonRunnerOptions):
            raise TypeError("'options' must be BasePythonRunnerOptions")

        start_time = monotonic()
        async with asyncio.timeout(options.timeout):
            if variables is None:
                output = await implementation.execute(input)
            else:
                output = await implementation.execute(input, variables=variables)
        duration = monotonic() - start_time

        return RunResult(
            output=output,
            meta=InlinePythonRunMeta(),
            duration=duration,
        )
