from dataclasses import dataclass

from fure.core.implementations import JinjaImplementation
from fure.core.run import SucceedRunMeta
from fure.core.runners.base import BaseRunner, BaseRunnerOptions


@dataclass(frozen=True, slots=True)
class BaseJinjaRunnerOptions(BaseRunnerOptions):
    timeout: float | None


class BaseJinjaRunner[
    RunnerOptionsT: BaseJinjaRunnerOptions = BaseJinjaRunnerOptions,
    RunMetaT: SucceedRunMeta = SucceedRunMeta,
](BaseRunner[JinjaImplementation, RunnerOptionsT, RunMetaT]): ...
