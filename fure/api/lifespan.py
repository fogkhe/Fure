from contextlib import asynccontextmanager

from fastapi import FastAPI

from fure.database.connection import Database
from fure.services.execution import ExecutionService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    app.state.database = None
    app.state.executions = None
    database = Database(settings.database_url.get_secret_value())
    executions = None
    try:
        if settings.database_auto_migrate:
            await database.migrate()
        await database.check()
        await database.check_schema()
        executions = ExecutionService(
            database,
            heartbeat_interval=settings.execution_heartbeat_interval,
            lease_seconds=settings.execution_lease_seconds,
        )
        await executions.start()
        app.state.database = database
        app.state.executions = executions
        async with app.state.mcp_http_app.lifespan(app):
            yield
    finally:
        app.state.executions = None
        app.state.database = None
        try:
            if executions is not None:
                await executions.stop()
        finally:
            await database.close()
