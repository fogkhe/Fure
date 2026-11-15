from abc import ABC, abstractmethod
from dataclasses import dataclass

from fure.core.implementations import BaseImplementation
from fure.core.run import SucceedRunMeta
from fure.core.types import JSONValue


@dataclass(frozen=True, slots=True)
class BaseRunnerOptions:
    timeout: float | None


@dataclass(frozen=True, slots=True)
class RunResult[RunMetaT: SucceedRunMeta = SucceedRunMeta]:
    output: JSONValue
    meta: RunMetaT
    duration: float


class BaseRunner[
    ImplementationT: BaseImplementation = BaseImplementation,
    RunnerOptionsT: BaseRunnerOptions = BaseRunnerOptions,
    RunMetaT: SucceedRunMeta = SucceedRunMeta,
](ABC):
    __slots__ = ("_options",)

    def __init__(
        self,
        options: RunnerOptionsT,
    ) -> None:
        self._options = options

    @abstractmethod
    async def run(
        self,
        implementation: ImplementationT,
        input: dict[str, JSONValue] | None,
        options: RunnerOptionsT | None = None,
    ) -> RunResult[RunMetaT]: ...
