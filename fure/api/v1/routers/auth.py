from fastapi import APIRouter, Request, Response

from fure.api.dependencies import SESSION_COOKIE, AuthServiceDep, PrincipalDep
from fure.api.v1.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    SessionResponse,
    session_response,
)
from fure.services.errors import Forbidden

router = APIRouter()


def private_response(response):
    response.headers["Cache-Control"] = "no-store"


@router.post("/login")
async def login(
    body: LoginRequest, request: Request, response: Response, service: AuthServiceDep
) -> SessionResponse:
    # Login has no existing CSRF token. Require a custom header so cross-origin
    # browser forms cannot submit credentials (no permissive CORS is configured).
    if request.headers.get("x-fure-client") != "web":
        raise Forbidden("Login requires X-Fure-Client: web")
    settings = request.app.state.settings
    secret, principal = await service.login(
        body.username,
        body.password.get_secret_value(),
        lifetime=settings.session_lifetime_seconds,
        previous_secret=request.cookies.get(SESSION_COOKIE),
    )
    response.set_cookie(
        SESSION_COOKIE,
        secret,
        max_age=settings.session_lifetime_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    private_response(response)
    return session_response(principal)


@router.get("/me")
async def me(principal: PrincipalDep, response: Response) -> SessionResponse:
    private_response(response)
    return session_response(principal)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    principal: PrincipalDep,
    service: AuthServiceDep,
):
    if principal.key_id is not None:
        raise Forbidden("Logout requires a browser session")
    await service.logout(request.cookies[SESSION_COOKIE])
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=request.app.state.settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    private_response(response)


@router.post("/password", status_code=204)
async def change_password(
    body: PasswordChangeRequest,
    request: Request,
    response: Response,
    principal: PrincipalDep,
    service: AuthServiceDep,
):
    await service.change_password(
        principal,
        current_password=body.current_password.get_secret_value(),
        new_password=body.new_password.get_secret_value(),
    )
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=request.app.state.settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    private_response(response)
