import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID, uuid7

from jinja2 import UndefinedError
from openai import APIError, APITimeoutError
from sqlalchemy import and_, or_, select, update

from fure.core.auth import Permission, Principal
from fure.core.errors import InputValidationError
from fure.core.run import CancelRunMeta, ErrorRunMeta, Run, RunStatus
from fure.core.runners import (
    InlinePythonRunner,
    OpenAIJinjaRunner,
    OpenAIJinjaRunnerOptions,
)
from fure.core.types import JSONValue
from fure.database.connection import Database
from fure.database.mappers import meta_to_data
from fure.database.models import RunRow
from fure.database.repositories import (
    ACTIVE_STATUSES,
    FunctionRepository,
    RunRepository,
)
from fure.services.errors import (
    Conflict,
    ExecutionCancelled,
    ExecutionFailed,
    ExecutionTimedOut,
    Forbidden,
    InvalidInput,
    NotFound,
    ProviderFailed,
    Unauthorized,
    Unavailable,
)

logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(
        self,
        database: Database,
        *,
        heartbeat_interval: float = 1.0,
        lease_seconds: float = 30.0,
    ) -> None:
        self.database = database
        self.worker_id = uuid7()
        self.heartbeat_interval = heartbeat_interval
        self.lease_seconds = lease_seconds
        self._tasks: dict[UUID, asyncio.Task[Run]] = {}
        self._monitor_task: asyncio.Task[None] | None = None
        self._closing = False

    async def start(self) -> None:
        await self._reap_stale()
        self._monitor_task = asyncio.create_task(
            self._monitor(), name="fure-execution-monitor"
        )

    async def stop(self) -> None:
        self._closing = True
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            await asyncio.gather(self._monitor_task, return_exceptions=True)
        tasks = list(self._tasks.values())
        try:
            now = datetime.now(UTC)
            async with self.database.sessions.begin() as session:
                await session.execute(
                    update(RunRow)
                    .where(
                        RunRow.worker_id == self.worker_id,
                        RunRow.status.in_(ACTIVE_STATUSES),
                    )
                    .values(
                        status=RunStatus.CANCELLED.value,
                        meta=meta_to_data(CancelRunMeta()),
                        finished_at=now,
                        updated_at=now,
                    )
                )
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                _, pending = await asyncio.wait(tasks, timeout=5)
                if pending:
                    logger.error(
                        "%s inline executions did not cooperate with cancellation",
                        len(pending),
                    )

    async def execute(
        self,
        name: str,
        input: dict[str, JSONValue] | None,
        *,
        principal: Principal | None = None,
    ) -> Run:
        if self._closing:
            raise Unavailable("Application is shutting down")
        async with self.database.sessions.begin() as session:
            function = await FunctionRepository(session).by_name(name, lock=True)
            if function is None:
                raise NotFound("Function not found or deleted")
            if not function.public:
                if principal is None:
                    raise Unauthorized("Authentication required")
                if not principal.allows(Permission.FUNCTIONS_RUN):
                    raise Forbidden("Permission required: functions.run")
            revision = function.revision
            if not function.runnable or revision is None:
                raise Conflict("Function is disabled or has no current revision")
            run = Run(
                revision,
                input,
                user_id=principal.user.id if principal else None,
                api_key_id=principal.key_id if principal else None,
            )
            await RunRepository(session).add(run, self.worker_id)
        if self._closing:
            await self._cancel_record(run.id)
            raise Unavailable("Application is shutting down", run_id=run.id)
        task = asyncio.create_task(self._perform(run), name=f"fure-run-{run.id}")
        self._tasks[run.id] = task
        task.add_done_callback(lambda finished: self._forget(run.id, finished))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                task.cancel()
                await asyncio.shield(self._cancel_record(run.id))
                raise
            async with self.database.sessions() as session:
                final = await RunRepository(session).get(run.id)
            if final is not None and final.status is RunStatus.SUCCEEDED:
                return final
            if final is not None and final.status is RunStatus.FAILED:
                raise ExecutionFailed(
                    "Execution worker stopped responding",
                    code="worker_lost",
                    run_id=run.id,
                ) from None
            raise ExecutionCancelled(
                "Execution was cancelled", code="cancelled", run_id=run.id
            ) from None

    def _forget(self, id: UUID, task: asyncio.Task[Run]) -> None:
        self._tasks.pop(id, None)
        if not task.cancelled():
            task.exception()

    async def cancel(self, id: UUID, *, principal: Principal) -> Run:
        async with self.database.sessions() as session:
            row = await session.get(RunRow, id)
            if row is None:
                raise NotFound("Run not found")
            if row.user_id == principal.user.id:
                if not principal.allows(Permission.RUNS_CANCEL):
                    raise Forbidden("Permission required: runs.cancel")
            elif not (
                principal.allows(Permission.RUNS_CANCEL_ALL)
                and principal.allows(Permission.RUNS_READ_ALL)
            ):
                raise NotFound("Run not found")
        await self._cancel_record(id, require_active=True)
        task = self._tasks.get(id)
        if task is not None:
            task.cancel()
        async with self.database.sessions() as session:
            run = await RunRepository(session).get(id)
            if run is None:
                raise NotFound("Run not found")
            return run

    async def _cancel_record(self, id: UUID, *, require_active: bool = False) -> None:
        now = datetime.now(UTC)
        async with self.database.sessions.begin() as session:
            repository = RunRepository(session)
            changed = await repository.transition(
                id,
                ACTIVE_STATUSES,
                status=RunStatus.CANCELLED.value,
                meta=meta_to_data(CancelRunMeta()),
                finished_at=now,
                updated_at=now,
            )
            if require_active and not changed:
                if (
                    await session.scalar(select(RunRow.id).where(RunRow.id == id))
                    is None
                ):
                    raise NotFound("Run not found")
                raise Conflict("Run has already finished")

    async def _perform(self, run: Run) -> Run:
        start = monotonic()
        try:
            run.start()
            async with self.database.sessions.begin() as session:
                changed = await RunRepository(session).transition(
                    run.id,
                    [RunStatus.PENDING.value],
                    status=RunStatus.RUNNING.value,
                    started_at=run.started_at,
                    updated_at=run.updated_at,
                    heartbeat_at=datetime.now(UTC),
                )
            if not changed:
                raise asyncio.CancelledError
            options = run.revision.runner_options
            runner = (
                OpenAIJinjaRunner(options)
                if isinstance(options, OpenAIJinjaRunnerOptions)
                else InlinePythonRunner(options)
            )
            async with asyncio.timeout(options.timeout):
                result = await runner.run(run.revision.implementation, run.input)
            json.dumps(result.output, allow_nan=False)
            run.succeed(result.output, result.meta, result.duration)
            async with self.database.sessions.begin() as session:
                changed = await RunRepository(session).transition(
                    run.id,
                    [RunStatus.RUNNING.value],
                    status=run.status.value,
                    output=run.output,
                    meta=meta_to_data(run.meta),
                    duration=run.duration,
                    finished_at=run.finished_at,
                    updated_at=run.updated_at,
                )
            if not changed:
                raise asyncio.CancelledError
            return run
        except asyncio.CancelledError:
            await asyncio.shield(self._cancel_record(run.id))
            raise
        except (Exception, SystemExit, KeyboardInterrupt) as error:
            if isinstance(error, (InputValidationError, UndefinedError)):
                failure = InvalidInput(str(error), code="invalid_input", run_id=run.id)
            elif isinstance(error, (TimeoutError, APITimeoutError)):
                failure = ExecutionTimedOut(
                    "Execution timed out", code="timeout", run_id=run.id
                )
            elif isinstance(error, APIError):
                failure = ProviderFailed(
                    "LLM provider request failed", code="provider_error", run_id=run.id
                )
            else:
                failure = ExecutionFailed(
                    "Function execution failed", code="execution_error", run_id=run.id
                )
            now = datetime.now(UTC)
            async with self.database.sessions.begin() as session:
                changed = await RunRepository(session).transition(
                    run.id,
                    ACTIVE_STATUSES,
                    status=RunStatus.FAILED.value,
                    meta=meta_to_data(ErrorRunMeta(failure.code, str(failure))),
                    duration=max(0, monotonic() - start),
                    finished_at=now,
                    updated_at=now,
                )
            if not changed:
                raise ExecutionCancelled(
                    "Execution was cancelled", code="cancelled", run_id=run.id
                ) from None
            raise failure from error

    async def _reap_stale(self) -> None:
        now = datetime.now(UTC)
        async with self.database.sessions.begin() as session:
            await session.execute(
                update(RunRow)
                .where(
                    RunRow.status.in_(ACTIVE_STATUSES),
                    or_(
                        RunRow.heartbeat_at
                        < now - timedelta(seconds=self.lease_seconds),
                        and_(
                            RunRow.heartbeat_at.is_(None),
                            RunRow.created_at
                            < now - timedelta(seconds=self.lease_seconds),
                        ),
                    ),
                )
                .values(
                    status=RunStatus.FAILED.value,
                    meta=meta_to_data(
                        ErrorRunMeta(
                            "worker_lost", "Execution worker stopped responding"
                        )
                    ),
                    finished_at=now,
                    updated_at=now,
                )
            )

    async def _monitor(self) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            try:
                ids = list(self._tasks)
                if ids:
                    async with self.database.sessions.begin() as session:
                        await session.execute(
                            update(RunRow)
                            .where(
                                RunRow.worker_id == self.worker_id,
                                RunRow.id.in_(ids),
                                RunRow.status.in_(ACTIVE_STATUSES),
                            )
                            .values(heartbeat_at=datetime.now(UTC))
                        )
                        stopped = (
                            await session.scalars(
                                select(RunRow.id).where(
                                    RunRow.id.in_(ids),
                                    or_(
                                        RunRow.status == RunStatus.CANCELLED.value,
                                        and_(
                                            RunRow.status == RunStatus.FAILED.value,
                                            RunRow.meta["code"].as_string()
                                            == "worker_lost",
                                        ),
                                    ),
                                )
                            )
                        ).all()
                    for id in stopped:
                        task = self._tasks.get(id)
                        if task is not None:
                            task.cancel()
                await self._reap_stale()
            except Exception:
                logger.exception("Execution heartbeat failed; will retry")
