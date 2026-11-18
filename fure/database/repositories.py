from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fure.core.function import Function
from fure.core.revision import Revision
from fure.core.run import Run, RunStatus
from fure.database.mappers import (
    function_from_row,
    implementation_to_data,
    meta_to_data,
    options_to_data,
    revision_from_row,
    run_from_row,
)
from fure.database.models import FunctionRow, RevisionRow, RunRow
from fure.services.errors import Conflict

ACTIVE_STATUSES = (RunStatus.PENDING.value, RunStatus.RUNNING.value)


async def paginate(session, statement, filters, page, size):
    statement = statement.where(*filters)
    total = await session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    rows = (await session.scalars(statement.offset(page * size).limit(size))).all()
    return rows, total


class FunctionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._versions: dict[UUID, int] = {}

    async def get(self, id: UUID, *, lock: bool = False) -> Function | None:
        statement = (
            select(FunctionRow)
            .options(selectinload(FunctionRow.revision))
            .where(FunctionRow.id == id)
        )
        if lock:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        if row is None:
            return None
        self._versions[row.id] = row.version
        return function_from_row(row)

    async def by_name(self, name: str, *, lock: bool = False) -> Function | None:
        statement = (
            select(FunctionRow)
            .options(selectinload(FunctionRow.revision))
            .where(FunctionRow.name == name, FunctionRow.deleted_at.is_(None))
        )
        if lock:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        if row is None:
            return None
        self._versions[row.id] = row.version
        return function_from_row(row)

    async def list(
        self, *, page, size, name=None, enabled=None, deleted=False, function_ids=None
    ):
        filters = [
            FunctionRow.deleted_at.is_not(None)
            if deleted
            else FunctionRow.deleted_at.is_(None)
        ]
        if name is not None:
            filters.append(FunctionRow.name.icontains(name, autoescape=True))
        if enabled is not None:
            filters.append(FunctionRow.enabled == enabled)
        if function_ids is not None:
            filters.append(FunctionRow.id.in_(function_ids))
        rows, total = await paginate(
            self.session,
            select(FunctionRow)
            .options(selectinload(FunctionRow.revision))
            .order_by(FunctionRow.created_at.desc(), FunctionRow.id.desc()),
            filters,
            page,
            size,
        )
        return [function_from_row(row) for row in rows], total

    async def add(self, function: Function) -> None:
        self.session.add(
            FunctionRow(
                id=function.id,
                name=function.name,
                description=function.description,
                revision_id=function.revision.id if function.revision else None,
                enabled=function.enabled,
                public=function.public,
                created_at=function.created_at,
                updated_at=function.updated_at,
                deleted_at=function.deleted_at,
                version=1,
            )
        )
        await self.session.flush()

    async def save(self, function: Function) -> None:
        version = self._versions[function.id]
        result = await self.session.execute(
            update(FunctionRow)
            .where(
                FunctionRow.id == function.id,
                FunctionRow.version == version,
            )
            .values(
                name=function.name,
                description=function.description,
                revision_id=function.revision.id if function.revision else None,
                enabled=function.enabled,
                public=function.public,
                updated_at=function.updated_at,
                deleted_at=function.deleted_at,
                version=version + 1,
            )
        )
        if result.rowcount != 1:
            raise Conflict("Function was changed concurrently; retry the request")
        self._versions[function.id] = version + 1


class RevisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: UUID) -> Revision | None:
        row = await self.session.scalar(
            select(RevisionRow)
            .options(selectinload(RevisionRow.function))
            .where(RevisionRow.id == id)
        )
        return None if row is None else revision_from_row(row)

    async def list(self, *, page, size, function_id=None, function_ids=None):
        filters = (
            [] if function_id is None else [RevisionRow.function_id == function_id]
        )
        if function_ids is not None:
            filters.append(RevisionRow.function_id.in_(function_ids))
        rows, total = await paginate(
            self.session,
            select(RevisionRow)
            .options(selectinload(RevisionRow.function))
            .order_by(RevisionRow.created_at.desc(), RevisionRow.id.desc()),
            filters,
            page,
            size,
        )
        return [revision_from_row(row) for row in rows], total

    async def add(self, revision: Revision) -> None:
        self.session.add(
            RevisionRow(
                id=revision.id,
                function_id=revision.function.id,
                implementation=implementation_to_data(revision.implementation),
                runner_options=options_to_data(revision.runner_options),
                created_at=revision.created_at,
            )
        )
        await self.session.flush()


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: UUID) -> Run | None:
        row = await self.session.scalar(
            select(RunRow)
            .options(selectinload(RunRow.revision).selectinload(RevisionRow.function))
            .where(RunRow.id == id)
        )
        return None if row is None else run_from_row(row)

    async def list(
        self,
        *,
        page,
        size,
        function_id=None,
        revision_id=None,
        status=None,
        user_id=None,
        function_ids=None,
    ):
        filters = []
        if function_ids is not None:
            filters.append(RevisionRow.function_id.in_(function_ids))
        if user_id is not None:
            filters.append(RunRow.user_id == user_id)
        if function_id is not None:
            filters.append(RevisionRow.function_id == function_id)
        if revision_id is not None:
            filters.append(RunRow.revision_id == revision_id)
        if status is not None:
            filters.append(RunRow.status == status)
        rows, total = await paginate(
            self.session,
            select(RunRow)
            .join(RevisionRow)
            .options(selectinload(RunRow.revision).selectinload(RevisionRow.function))
            .order_by(RunRow.created_at.desc(), RunRow.id.desc()),
            filters,
            page,
            size,
        )
        return [run_from_row(row) for row in rows], total

    async def add(self, run: Run, worker_id: UUID) -> None:
        self.session.add(
            RunRow(
                id=run.id,
                revision_id=run.revision.id,
                user_id=run.user_id,
                api_key_id=run.api_key_id,
                input=run.input,
                status=run.status.value,
                output=run.output,
                meta=meta_to_data(run.meta),
                duration=run.duration,
                started_at=run.started_at,
                finished_at=run.finished_at,
                created_at=run.created_at,
                updated_at=run.updated_at,
                worker_id=worker_id,
                heartbeat_at=datetime.now(UTC),
            )
        )
        await self.session.flush()

    async def transition(self, id: UUID, from_statuses, **values) -> bool:
        result = await self.session.execute(
            update(RunRow)
            .where(
                RunRow.id == id,
                RunRow.status.in_(from_statuses),
            )
            .values(**values)
        )
        return result.rowcount == 1
