from datetime import UTC, datetime
from typing import Self
from uuid import UUID, uuid7

from fure.core.function import Function
from fure.core.implementations import (
    BaseImplementation,
    JinjaImplementation,
    PythonImplementation,
)
from fure.core.runners import BaseRunnerOptions
from fure.core.runners.jinja.base import BaseJinjaRunnerOptions
from fure.core.runners.python.base import BasePythonRunnerOptions
from fure.utils.datetime import normalize_datetime


class Revision:
    __slots__ = (
        "_created_at",
        "_function",
        "_id",
        "_implementation",
        "_runner_options",
    )

    def __init__(
        self,
        implementation: BaseImplementation,
        runner_options: BaseRunnerOptions,
        function: Function,
        *,
        id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> None:
        if not (
            (
                isinstance(implementation, PythonImplementation)
                and isinstance(runner_options, BasePythonRunnerOptions)
            )
            or (
                isinstance(implementation, JinjaImplementation)
                and isinstance(runner_options, BaseJinjaRunnerOptions)
            )
        ):
            raise TypeError(
                f"'runner_options' ({type(runner_options).__name__}) are incompatible "
                f"with 'implementation' ({type(implementation).__name__})"
            )

        self._id = id if id is not None else uuid7()
        self._function = function
        self._implementation = implementation
        self._runner_options = runner_options
        self._created_at = normalize_datetime(
            created_at if created_at is not None else datetime.now(UTC)
        )

    @classmethod
    def restore(
        cls,
        *,
        id: UUID,
        implementation: BaseImplementation,
        runner_options: BaseRunnerOptions,
        function: Function,
        created_at: datetime,
    ) -> Self:
        revision = cls.__new__(cls)
        revision._id = id
        revision._implementation = implementation
        revision._runner_options = runner_options
        revision._function = function
        revision._created_at = created_at
        return revision

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Revision):
            return False

        return self._id == value._id

    def __hash__(self) -> int:
        return hash(self._id)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def function(self) -> Function:
        return self._function

    @property
    def implementation(self) -> BaseImplementation:
        return self._implementation

    @property
    def runner_options(self) -> BaseRunnerOptions:
        return self._runner_options

    @property
    def created_at(self) -> datetime:
        return self._created_at
