import asyncio
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import asyncpg
from sqlalchemy.engine import make_url


async def _admin_sql(url, statement):
    connection = await asyncpg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False),
        timeout=10,
    )
    try:
        await connection.execute(statement)
    finally:
        await connection.close()


@contextmanager
def isolated_database():
    """Use a temporary SQLite file or a uniquely owned PostgreSQL test database."""
    external = os.environ.get("FURE_TEST_DATABASE_URL")
    if external is None:
        with TemporaryDirectory() as directory:
            yield "sqlite+aiosqlite:///" + (Path(directory) / "fure.db").as_posix()
        return
    url = make_url(external)
    if url.get_backend_name() != "postgresql":
        raise ValueError(
            "FURE_TEST_DATABASE_URL must point to a PostgreSQL test server"
        )
    name = "fure_test_" + uuid4().hex
    asyncio.run(_admin_sql(url, f'CREATE DATABASE "{name}"'))
    try:
        yield url.set(database=name).render_as_string(hide_password=False)
    finally:
        asyncio.run(_admin_sql(url, f'DROP DATABASE "{name}" WITH (FORCE)'))
