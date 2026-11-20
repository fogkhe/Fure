import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fure.core.auth import Permission, Principal
from fure.core.function import Function
from fure.core.implementations import BaseImplementation
from fure.core.revision import Revision
from fure.core.run import Run
from fure.core.runners import BaseRunnerOptions
from fure.core.runners.jinja.openai import OpenAIJinjaRunnerOptions
from fure.database.mappers import implementation_to_data
from fure.database.repositories import (
    FunctionRepository,
    RevisionRepository,
    RunRepository,
)
from fure.services.auth import require_function_access
from fure.services.errors import Conflict, InvalidInput, NotFound


@asynccontextmanager
async def transaction(session):
    try:
        async with session.begin():
            yield
    except IntegrityError as error:
        raise Conflict(
            "Function name is already in use or referenced state changed"
        ) from error


async def require_function(
    repository: FunctionRepository, id: UUID, *, lock: bool = False
) -> Function:
    function = await repository.get(id, lock=lock)
    if function is None:
        raise NotFound("Function not found")
    return function


class FunctionService:
    def __init__(
        self, session: AsyncSession, principal: Principal | None = None
    ) -> None:
        self.principal = principal
        self.session = session
        self.functions = FunctionRepository(session)
        self.revisions = RevisionRepository(session)

    async def list(self, **filters) -> tuple[list[Function], int]:
        if self.principal is not None and self.principal.key_id is not None:
            filters["function_ids"] = self.principal.function_ids or frozenset()
        async with transaction(self.session):
            return await self.functions.list(**filters)

    async def get(self, id: UUID) -> Function:
        require_function_access(self.principal, id)
        async with transaction(self.session):
            return await require_function(self.functions, id)

    async def create(
        self,
        *,
        name: str,
        description: str | None = None,
        enabled: bool = True,
        public: bool = False,
    ) -> Function:
        function = Function(name, description, enabled=enabled, public=public)
        async with transaction(self.session):
            await self.functions.add(function)
        return function

    async def update(self, id: UUID, changes: dict) -> Function:
        require_function_access(self.principal, id)
        async with transaction(self.session):
            function = await require_function(self.functions, id, lock=True)
            if function.deleted:
                raise Conflict("Undelete the function before editing it")
            if "name" in changes:
                function.name = changes["name"]
            if "description" in changes:
                function.description = changes["description"]
            if "enabled" in changes:
                function.enable() if changes["enabled"] else function.disable()
            if "public" in changes:
                function.public = changes["public"]
            if "revision_id" in changes:
                revision = await self.revisions.get(changes["revision_id"])
                if revision is None:
                    raise NotFound("Revision not found")
                if revision.function.id != function.id:
                    raise Conflict("Revision belongs to another function")
                revision = Revision.restore(
                    id=revision.id,
                    function=function,
                    implementation=revision.implementation,
                    runner_options=revision.runner_options,
                    created_at=revision.created_at,
                )
                function.revision = revision
            await self.functions.save(function)
        return function

    async def delete(self, id: UUID) -> None:
        require_function_access(self.principal, id)
        async with transaction(self.session):
            function = await require_function(self.functions, id, lock=True)
            function.delete()
            await self.functions.save(function)

    async def undelete(self, id: UUID) -> Function:
        require_function_access(self.principal, id)
        async with transaction(self.session):
            function = await require_function(self.functions, id, lock=True)
            function.undelete()
            await self.functions.save(function)
        return function


class RevisionService:
    def __init__(
        self, session: AsyncSession, principal: Principal | None = None
    ) -> None:
        self.principal = principal
        self.session = session
        self.revisions = RevisionRepository(session)
        self.functions = FunctionRepository(session)

    async def list(self, **filters) -> tuple[list[Revision], int]:
        if self.principal is not None and self.principal.key_id is not None:
            filters["function_ids"] = self.principal.function_ids or frozenset()
        async with transaction(self.session):
            return await self.revisions.list(**filters)

    async def get(self, id: UUID) -> Revision:
        async with transaction(self.session):
            revision = await self.revisions.get(id)
            if revision is None:
                raise NotFound("Revision not found")
            require_function_access(self.principal, revision.function.id)
            return revision

    async def create(
        self,
        *,
        function_id: UUID,
        implementation: BaseImplementation,
        runner_options: BaseRunnerOptions,
    ) -> Revision:
        require_function_access(self.principal, function_id)
        async with transaction(self.session):
            function = await require_function(self.functions, function_id)
            if function.deleted:
                raise Conflict("Function is deleted")
        try:
            # User definitions are analyzed explicitly on creation, never on reads.
            # Keep module initialization off the API event loop and outside a DB transaction.
            await asyncio.to_thread(implementation_to_data, implementation)
        except (Exception, SystemExit, KeyboardInterrupt) as error:
            raise InvalidInput("Invalid implementation definition") from error
        async with transaction(self.session):
            function = await require_function(self.functions, function_id, lock=True)
            if function.deleted:
                raise Conflict("Function is deleted")
            if (
                isinstance(runner_options, OpenAIJinjaRunnerOptions)
                and runner_options.tool_function_ids
            ):
                ids = runner_options.tool_function_ids
                if function_id in ids:
                    raise InvalidInput("A function cannot be its own tool")
                for id in ids:
                    require_function_access(self.principal, id)
                tools = await self.functions.get_many(ids)
                if len(tools) != len(ids):
                    raise NotFound("Tool function not found or deleted")
            try:
                revision = Revision(implementation, runner_options, function)
            except TypeError as error:
                raise InvalidInput(str(error)) from error
            await self.revisions.add(revision)
        return revision


class RunService:
    def __init__(
        self, session: AsyncSession, principal: Principal | None = None
    ) -> None:
        self.session = session
        self.runs = RunRepository(session)
        self.principal = principal

    async def list(self, **filters) -> tuple[list[Run], int]:
        if (parent_run_id := filters.get("parent_run_id")) is not None:
            await self.get(parent_run_id)
        if self.principal is not None and self.principal.key_id is not None:
            filters["function_ids"] = self.principal.function_ids or frozenset()
        if self.principal is not None and not self.principal.allows(
            Permission.RUNS_READ_ALL
        ):
            filters["user_id"] = self.principal.user.id
        async with transaction(self.session):
            return await self.runs.list(**filters)

    async def get(self, id: UUID) -> Run:
        async with transaction(self.session):
            run = await self.runs.get(id)
            if run is None:
                raise NotFound("Run not found")
            require_function_access(self.principal, run.revision.function.id)
            if (
                self.principal is not None
                and not self.principal.allows(Permission.RUNS_READ_ALL)
                and run.user_id != self.principal.user.id
            ):
                raise NotFound("Run not found")
            return run
