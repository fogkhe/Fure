from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Self
from uuid import UUID, uuid7

from fure.core.types import JSONValue
from fure.utils.datetime import normalize_datetime

if TYPE_CHECKING:
    from fure.core.revision import Revision


@dataclass(frozen=True, slots=True)
class BaseRunMeta: ...


@dataclass(frozen=True, slots=True)
class SucceedRunMeta(BaseRunMeta): ...


@dataclass(frozen=True, slots=True)
class FailRunMeta(BaseRunMeta): ...


@dataclass(frozen=True, slots=True)
class CancelRunMeta(BaseRunMeta): ...


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Run:
    __slots__ = (
        "_created_at",
        "_duration",
        "_finished_at",
        "_id",
        "_input",
        "_meta",
        "_output",
        "_revision",
        "_started_at",
        "_status",
        "_updated_at",
    )

    def __init__(
        self,
        revision: Revision,
        input: dict[str, JSONValue] | None,
        *,
        id: UUID | None = None,
        status: RunStatus | None = None,
        output: JSONValue | None = None,
        meta: BaseRunMeta | None = None,
        duration: float | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self._id = id if id is not None else uuid7()
        self._revision = revision
        self._input = deepcopy(input) if input is not None else None
        self._status = status if status is not None else RunStatus.PENDING
        self._output = deepcopy(output)
        self._meta = deepcopy(meta) if meta is not None else None
        self._duration = duration
        self._started_at = (
            normalize_datetime(started_at) if started_at is not None else None
        )
        self._finished_at = (
            normalize_datetime(finished_at) if finished_at is not None else None
        )
        self._created_at = normalize_datetime(
            created_at if created_at is not None else datetime.now(UTC)
        )
        self._updated_at = (
            normalize_datetime(updated_at)
            if updated_at is not None
            else self._created_at
        )

    @classmethod
    def restore(
        cls,
        *,
        id: UUID,
        revision: Revision,
        input: dict[str, JSONValue] | None,
        status: RunStatus,
        output: JSONValue,
        meta: BaseRunMeta | None,
        duration: float | None,
        started_at: datetime | None,
        finished_at: datetime | None,
        created_at: datetime,
        updated_at: datetime,
    ) -> Self:
        run = cls.__new__(cls)
        run._id = id
        run._revision = revision
        run._input = deepcopy(input)
        run._status = status
        run._output = deepcopy(output)
        run._meta = deepcopy(meta)
        run._duration = duration
        run._started_at = started_at
        run._finished_at = finished_at
        run._created_at = created_at
        run._updated_at = updated_at
        return run

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def revision(self) -> Revision:
        return self._revision

    @property
    def input(self) -> dict[str, JSONValue] | None:
        return deepcopy(self._input) if self._input is not None else None

    @property
    def status(self) -> RunStatus:
        return self._status

    @property
    def output(self) -> JSONValue:
        return deepcopy(self._output)

    @property
    def meta(self) -> BaseRunMeta | None:
        return deepcopy(self._meta) if self._meta is not None else None

    @property
    def duration(self) -> float | None:
        return self._duration

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    @property
    def finished_at(self) -> datetime | None:
        return self._finished_at

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    def start(self) -> None:
        if self._status != RunStatus.PENDING:
            raise ValueError(
                f"status must be {RunStatus.PENDING.value!r} to start run",
            )

        self._status = RunStatus.RUNNING
        self._started_at = normalize_datetime(datetime.now(UTC))
        self._update()

    def succeed(
        self,
        output: JSONValue,
        meta: SucceedRunMeta | None,
        duration: float,
    ) -> None:
        if self._status is not RunStatus.RUNNING:
            raise ValueError(
                f"status must be {RunStatus.RUNNING.value!r} to succeed run",
            )

        self._status = RunStatus.SUCCEEDED
        self._output = deepcopy(output)
        self._meta = deepcopy(meta) if meta is not None else None
        self._duration = duration
        self._finish()
        self._update()

    def fail(
        self,
        meta: FailRunMeta,
        duration: float | None,
    ) -> None:
        if self._status not in (RunStatus.PENDING, RunStatus.RUNNING):
            raise ValueError(
                f"status must be {RunStatus.PENDING.value!r} "
                f"or {RunStatus.RUNNING.value!r} to fail run",
            )

        self._status = RunStatus.FAILED
        self._meta = deepcopy(meta)
        self._duration = duration
        self._finish()
        self._update()

    def cancel(
        self,
        meta: CancelRunMeta,
        duration: float | None,
    ) -> None:
        if self._status not in (RunStatus.PENDING, RunStatus.RUNNING):
            raise ValueError(
                f"status must be {RunStatus.PENDING.value!r} "
                f"or {RunStatus.RUNNING.value!r} to cancel run",
            )

        self._status = RunStatus.CANCELLED
        self._meta = deepcopy(meta)
        self._duration = duration
        self._finish()
        self._update()

    def _finish(self) -> None:
        self._finished_at = normalize_datetime(datetime.now(UTC))

    def _update(self) -> None:
        self._updated_at = normalize_datetime(datetime.now(UTC))
