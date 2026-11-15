import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(
            url,
            pool_pre_ping=True,
            hide_parameters=True,
            json_serializer=lambda value: json.dumps(value, allow_nan=False),
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine.sync_engine, "connect", self._configure_sqlite)

    @staticmethod
    def _configure_sqlite(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

    async def migrate(self) -> None:
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).parent / "migrations")
        )
        async with self.engine.connect() as connection:
            if self.engine.dialect.name == "sqlite":
                await connection.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                await connection.begin()
                await connection.execute(
                    text("SELECT pg_advisory_xact_lock(728342198)")
                )
            try:

                def upgrade(sync_connection):
                    config.attributes["connection"] = sync_connection
                    command.upgrade(config, "head")

                await connection.run_sync(upgrade)
                await connection.commit()
            except BaseException:
                await connection.rollback()
                raise

    async def check(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def check_schema(self) -> None:
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).parent / "migrations")
        )
        expected = set(ScriptDirectory.from_config(config).get_heads())
        async with self.engine.connect() as connection:
            actual = set(
                (
                    await connection.scalars(
                        text("SELECT version_num FROM alembic_version")
                    )
                ).all()
            )
        if actual != expected:
            raise RuntimeError(
                "Database migrations are not up to date; run alembic upgrade head"
            )

    async def close(self) -> None:
        await self.engine.dispose()
