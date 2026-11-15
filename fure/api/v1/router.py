from fastapi import APIRouter

from fure.api.v1.routers import (
    functions,
    revisions,
    run,
    runs,
)
from fure.api.v1.schemas import ErrorResponse

router = APIRouter(
    responses={
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
