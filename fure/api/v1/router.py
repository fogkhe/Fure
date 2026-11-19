from fastapi import APIRouter

from fure.api.v1.routers import (
    auth,
    functions,
    keys,
    revisions,
    roles,
    run,
    runs,
    users,
    variables,
)
from fure.api.v1.schemas import ErrorResponse

router = APIRouter(
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Authentication required or invalid credentials",
        },
        403: {
            "model": ErrorResponse,
            "description": "Insufficient permissions or invalid CSRF token",
        },
        422: {
            "model": ErrorResponse,
            "description": "Request or function input validation failed",
        },
        503: {
            "model": ErrorResponse,
            "description": "Database unavailable or application shutting down",
        },
    }
)

router.include_router(functions.router, prefix="/functions", tags=["functions"])
router.include_router(revisions.router, prefix="/revisions", tags=["revisions"])
router.include_router(runs.router, prefix="/runs", tags=["runs"])
router.include_router(run.router, prefix="/run", tags=["run"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(roles.router, prefix="/roles", tags=["roles"])
router.include_router(keys.router, prefix="/keys", tags=["keys"])
router.include_router(variables.router, prefix="/variables", tags=["variables"])
