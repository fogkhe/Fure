import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from fure.api import (
    health,
    v1,
)
from fure.api.lifespan import lifespan
from fure.services.errors import (
    Conflict,
    ExecutionCancelled,
    ExecutionFailed,
    ExecutionTimedOut,
    InvalidInput,
    NotFound,
    ProviderFailed,
    ServiceError,
    Unavailable,
)
from fure.settings import Settings, settings

logger = logging.getLogger(__name__)


def create_app(configuration: Settings | None = None) -> FastAPI:
    application = FastAPI(title="Fure", version="0.1.0", lifespan=lifespan)
    application.state.settings = (
        configuration if configuration is not None else settings
    )
    application.include_router(v1.router, prefix="/v1")
    application.include_router(health.router)

    @application.exception_handler(ServiceError)
    async def service_error(_request: Request, error: ServiceError):
        codes = {
            NotFound: 404,
            Conflict: 409,
            InvalidInput: 422,
            ExecutionCancelled: 409,
            ExecutionFailed: 500,
            ProviderFailed: 502,
            ExecutionTimedOut: 504,
            Unavailable: 503,
        }
        headers = {"X-Run-Id": str(error.run_id)} if error.run_id is not None else None
        return JSONResponse(
            status_code=codes.get(type(error), 500),
            content={"detail": str(error)},
            headers=headers,
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, _error: SQLAlchemyError):
        logger.exception("Database operation failed")
        return JSONResponse(
            status_code=503, content={"detail": "Database is unavailable"}
        )

    @application.exception_handler(Exception)
    async def unexpected_error(_request: Request, _error: Exception):
        logger.exception("Unhandled application error")
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )

    return application


app = create_app()
