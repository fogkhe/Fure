from dataclasses import dataclass

from fure.core.implementations import PythonImplementation
from fure.core.run import SucceedRunMeta
from fure.core.runners.base import BaseRunner, BaseRunnerOptions


@dataclass(frozen=True, slots=True)
class BasePythonRunnerOptions(BaseRunnerOptions):
    timeout: float | None


class BasePythonRunner[
    RunnerOptionsT: BasePythonRunnerOptions = BasePythonRunnerOptions,
    RunMetaT: SucceedRunMeta = SucceedRunMeta,
](BaseRunner[PythonImplementation, RunnerOptionsT, RunMetaT]): ...
