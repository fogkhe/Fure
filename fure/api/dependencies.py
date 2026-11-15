from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from fure.database.connection import Database
from fure.services.errors import Unavailable
from fure.services.execution import ExecutionService
from fure.services.resources import FunctionService, RevisionService, RunService


def get_database(request: Request) -> Database:
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise Unavailable("Application has not started")
    return database


async def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async with database.sessions() as session:
        yield session


type SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_function_service(session: SessionDep) -> FunctionService:
    return FunctionService(session)


def get_revision_service(session: SessionDep) -> RevisionService:
    return RevisionService(session)


def get_run_service(session: SessionDep) -> RunService:
    return RunService(session)


def get_execution_service(request: Request) -> ExecutionService:
    executions = getattr(request.app.state, "executions", None)
    if executions is None:
        raise Unavailable("Application has not started")
    return executions


type FunctionServiceDep = Annotated[FunctionService, Depends(get_function_service)]
type RevisionServiceDep = Annotated[RevisionService, Depends(get_revision_service)]
type RunServiceDep = Annotated[RunService, Depends(get_run_service)]
type ExecutionServiceDep = Annotated[ExecutionService, Depends(get_execution_service)]
