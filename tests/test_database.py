import asyncio
import io
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid7

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import IntegrityError

from fure.core.implementations import PythonImplementation
from fure.core.run import Run, RunStatus
from fure.core.runners.python.inline import InlinePythonRunnerOptions
from fure.database.connection import Database
from fure.database.models import Base, FunctionRow, RunRow
from fure.database.repositories import FunctionRepository, RunRepository
from fure.services.errors import Conflict, ExecutionCancelled
from fure.services.execution import ExecutionService
from fure.services.resources import FunctionService, RevisionService
from tests.database_support import isolated_database


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = isolated_database()
        url = await asyncio.to_thread(self.storage.__enter__)
        self.addAsyncCleanup(asyncio.to_thread, self.storage.__exit__, None, None, None)
        self.database = Database(url)
        self.addAsyncCleanup(self.database.close)
        await self.database.migrate()

    async def configured_function(
        self, code="async def function(input: None) -> str: return 'ok'"
    ):
        async with self.database.sessions() as session:
            functions = FunctionService(session)
            function = await functions.create(name="test")
            revision = await RevisionService(session).create(
                function_id=function.id,
                implementation=PythonImplementation(code),
                runner_options=InlinePythonRunnerOptions(timeout=5),
            )
            return await functions.update(function.id, {"revision_id": revision.id})

    async def test_migration_is_idempotent_and_foreign_keys_are_enforced(self):
        await self.database.migrate()
        await self.database.check_schema()
        async with self.database.engine.connect() as connection:
            tables = await connection.run_sync(
                lambda sync: inspect(sync).get_table_names()
            )
            foreign_keys = await connection.run_sync(
                lambda sync: inspect(sync).get_foreign_keys("functions")
            )
        self.assertTrue(
            {"functions", "revisions", "runs", "alembic_version"}.issubset(tables)
        )
        self.assertTrue(
            any(item["referred_table"] == "revisions" for item in foreign_keys)
        )
        function = await self.configured_function()
        with self.assertRaises(IntegrityError):
            async with self.database.sessions.begin() as session:
                await session.execute(
                    update(FunctionRow)
                    .where(FunctionRow.id == function.id)
                    .values(revision_id=uuid7())
                )

    async def test_optimistic_lock_prevents_lost_updates(self):
        function = await self.configured_function()
        async with (
            self.database.sessions() as first,
            self.database.sessions() as second,
        ):
            repository = FunctionRepository(first)
            async with first.begin():
                stale = await repository.get(function.id)
            await FunctionService(second).update(function.id, {"name": "new_name"})
            stale.description = "would overwrite newer data"
            with self.assertRaises(Conflict):
                async with first.begin():
                    await repository.save(stale)
        async with self.database.sessions() as session:
            current = await FunctionRepository(session).get(function.id)
        self.assertEqual(current.name, "new_name")
        self.assertIsNone(current.description)

    async def test_stale_recovery_preserves_live_and_completed_runs(self):
        function = await self.configured_function()
        worker = uuid7()
        runs = [Run(function.revision, None) for _ in range(3)]
        async with self.database.sessions.begin() as session:
            repository = RunRepository(session)
            for run in runs:
                await repository.add(run, worker)
            await session.execute(
                update(RunRow)
                .where(RunRow.id.in_([runs[0].id, runs[2].id]))
                .values(heartbeat_at=datetime.now(UTC) - timedelta(minutes=2))
            )
            await session.execute(
                update(RunRow)
                .where(RunRow.id == runs[2].id)
                .values(status="succeeded", output="complete")
            )
        service = ExecutionService(
            self.database, heartbeat_interval=0.02, lease_seconds=10
        )
        await service.start()
        try:
            async with self.database.sessions() as session:
                repository = RunRepository(session)
                stale, live, complete = [await repository.get(run.id) for run in runs]
            self.assertIs(stale.status, RunStatus.FAILED)
            self.assertEqual(stale.meta.code, "worker_lost")
            self.assertIsNotNone(stale.finished_at)
            self.assertIs(live.status, RunStatus.PENDING)
            self.assertIs(complete.status, RunStatus.SUCCEEDED)
            self.assertEqual(complete.output, "complete")
        finally:
            await service.stop()

    async def wait_running(self):
        async with asyncio.timeout(3):
            while True:
                async with self.database.sessions() as session:
                    id = await session.scalar(
                        select(RunRow.id).where(RunRow.status == "running")
                    )
                if id is not None:
                    return id
                await asyncio.sleep(0.01)

    async def test_shutdown_cancels_owned_execution_and_rejects_new_work(self):
        await self.configured_function(
            "import asyncio\nasync def function(input: None) -> str:\n    await asyncio.sleep(10)\n    return 'late'"
        )
        service = ExecutionService(self.database, heartbeat_interval=0.02)
        await service.start()
        task = asyncio.create_task(service.execute("test", None))
        id = await self.wait_running()
        await service.stop()
        with self.assertRaises(ExecutionCancelled):
            await task
        async with self.database.sessions() as session:
            run = await RunRepository(session).get(id)
        self.assertIs(run.status, RunStatus.CANCELLED)
        self.assertIsNotNone(run.finished_at)
        self.assertFalse(service._tasks)
        from fure.services.errors import Unavailable

        with self.assertRaises(Unavailable):
            await service.execute("test", None)

    async def test_caller_cancellation_is_persisted(self):
        await self.configured_function(
            "import asyncio\nasync def function(input: None) -> str:\n    await asyncio.sleep(10)\n    return 'late'"
        )
        service = ExecutionService(self.database, heartbeat_interval=0.02)
        await service.start()
        try:
            task = asyncio.create_task(service.execute("test", None))
            id = await self.wait_running()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            async with self.database.sessions() as session:
                run = await RunRepository(session).get(id)
            self.assertIs(run.status, RunStatus.CANCELLED)
        finally:
            await service.stop()

    async def test_downgrade_and_upgrade(self):
        await self.configured_function()
        config = Config()
        config.set_main_option(
            "script_location",
            str(Path(__file__).resolve().parent.parent / "fure/database/migrations"),
        )
        async with self.database.engine.begin() as connection:

            def downgrade(sync):
                config.attributes["connection"] = sync
                command.downgrade(config, "base")

            await connection.run_sync(downgrade)
        await self.database.migrate()
        await self.database.check_schema()
        async with self.database.sessions() as session:
            self.assertEqual((await session.scalars(select(FunctionRow))).all(), [])

    async def test_outdated_schema_is_detected(self):
        async with self.database.engine.begin() as connection:
            await connection.execute(
                text("UPDATE alembic_version SET version_num = 'old'")
            )
        with self.assertRaisesRegex(RuntimeError, "not up to date"):
            await self.database.check_schema()

    async def test_migration_matches_orm_metadata(self):
        async with self.database.engine.connect() as connection:
            differences = await connection.run_sync(
                lambda sync: compare_metadata(
                    MigrationContext.configure(sync), Base.metadata
                )
            )
        self.assertEqual(differences, [])

    def test_postgresql_migration_compiles_without_a_server(self):
        buffer = io.StringIO()
        config = Config(output_buffer=buffer)
        config.set_main_option(
            "script_location",
            str(Path(__file__).resolve().parent.parent / "fure/database/migrations"),
        )
        config.set_main_option(
            "sqlalchemy.url", "postgresql+asyncpg://user:password@localhost/fure"
        )
        command.upgrade(config, "head", sql=True)
        sql = buffer.getvalue()
        self.assertIn("CREATE UNIQUE INDEX uq_functions_active_name", sql)
        self.assertIn("WHERE deleted_at IS NULL", sql)
        self.assertEqual(sql.count("ADD CONSTRAINT fk_functions_revision"), 1)


if __name__ == "__main__":
    unittest.main()
