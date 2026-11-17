import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from fure.core.auth import Permission, Principal
from fure.database.connection import Database
from fure.services.auth import AuthService, require
from fure.services.errors import Forbidden, Unauthorized, Unavailable
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


def get_auth_service(
    database: Annotated[Database, Depends(get_database)],
) -> AuthService:
    return AuthService(database)


type AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

SESSION_COOKIE = "fure_session"
bearer = HTTPBearer(auto_error=False, scheme_name="APIKey")
session_cookie = APIKeyCookie(
    name=SESSION_COOKIE, auto_error=False, scheme_name="Session"
)


async def get_optional_principal(
    request: Request,
    service: AuthServiceDep,
    authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    cookie: Annotated[str | None, Depends(session_cookie)],
) -> Principal | None:
    if "authorization" in request.headers:
        if authorization is None:
            raise Unauthorized("Use Authorization: Bearer <API key>")
        return await service.authenticate(authorization.credentials, api_key=True)
    if cookie is None:
        return None
    principal = await service.authenticate(cookie, api_key=False)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(supplied.encode(), principal.csrf_token.encode()):
            raise Forbidden("Invalid CSRF token")
    return principal


type OptionalPrincipalDep = Annotated[Principal | None, Depends(get_optional_principal)]


def get_principal(principal: OptionalPrincipalDep) -> Principal:
    if principal is None:
        raise Unauthorized("Authentication required")
    return principal


type PrincipalDep = Annotated[Principal, Depends(get_principal)]


def get_function_service(
    session: SessionDep, principal: PrincipalDep
) -> FunctionService:
    return FunctionService(session, principal)


def get_revision_service(
    session: SessionDep, principal: PrincipalDep
) -> RevisionService:
    return RevisionService(session, principal)


def require_permission(permission: Permission):
    def check(principal: PrincipalDep):
        require(principal, permission)
        return principal

    return check


def get_run_service(session: SessionDep, principal: PrincipalDep) -> RunService:
    return RunService(session, principal)


def get_execution_service(request: Request) -> ExecutionService:
    executions = getattr(request.app.state, "executions", None)
    if executions is None:
        raise Unavailable("Application has not started")
    return executions


type FunctionServiceDep = Annotated[FunctionService, Depends(get_function_service)]
type RevisionServiceDep = Annotated[RevisionService, Depends(get_revision_service)]
type RunServiceDep = Annotated[RunService, Depends(get_run_service)]
type ExecutionServiceDep = Annotated[ExecutionService, Depends(get_execution_service)]
