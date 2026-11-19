from contextlib import asynccontextmanager

from fastapi import FastAPI

from fure.database.connection import Database
from fure.services.execution import ExecutionService
from fure.services.variables import VariableService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    app.state.database = None
    app.state.executions = None
    app.state.variables = None
    database = Database(settings.database_url.get_secret_value())
    executions = None
    try:
        if settings.database_auto_migrate:
            await database.migrate()
        await database.check()
        await database.check_schema()
        key = settings.variables_encryption_key
        variables = VariableService(
            database, key.get_secret_value() if key is not None else None
        )
        executions = ExecutionService(
            database,
            variables=variables,
            heartbeat_interval=settings.execution_heartbeat_interval,
            lease_seconds=settings.execution_lease_seconds,
        )
        await executions.start()
        app.state.database = database
        app.state.executions = executions
        app.state.variables = variables
        async with app.state.mcp_http_app.lifespan(app):
            yield
    finally:
        app.state.executions = None
        app.state.variables = None
        app.state.database = None
        try:
            if executions is not None:
                await executions.stop()
        finally:
            await database.close()
