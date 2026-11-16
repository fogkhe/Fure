"""Backend fixture used only by Playwright, with a fresh isolated database."""

import asyncio

import uvicorn

from fure.database.connection import Database
from fure.services.auth import AuthService
from fure.settings import settings


async def prepare():
    database = Database(settings.database_url.get_secret_value())
    try:
        await database.migrate()
        await AuthService(database).create_first_admin(
            "admin", "fure-browser-test-password"
        )
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(prepare())
    uvicorn.run("fure.api:app", host="127.0.0.1", port=8011)
