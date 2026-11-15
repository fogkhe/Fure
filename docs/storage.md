# Storage and application lifecycle

Fure uses SQLAlchemy async sessions with SQLite (`aiosqlite`) or PostgreSQL
(`asyncpg`). By default it creates `data/fure.db`. Set `DATABASE_URL` to use another
database, for example `postgresql+asyncpg://user:password@localhost:5432/fure`.

Start the API with:

```sh
uv run uvicorn fure.api:app --host 0.0.0.0 --port 8000
```

The lifespan creates the engine and session factory, applies Alembic migrations,
checks the schema version, starts the execution monitor, and releases resources
on shutdown. Migration startup is serialized using PostgreSQL transaction advisory
locks or SQLite `BEGIN IMMEDIATE`, including multiple application workers.

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | SQLite in `data/fure.db` | SQLAlchemy async connection URL |
| `DATABASE_AUTO_MIGRATE` | `true` | Apply Alembic migrations during startup |
| `EXECUTION_HEARTBEAT_INTERVAL` | `1` | Worker heartbeat interval in seconds |
| `EXECUTION_LEASE_SECONDS` | `30` | Mark active executions failed after this many seconds without a heartbeat |

The lease must exceed three heartbeat intervals and be at least ten seconds.
With `DATABASE_AUTO_MIGRATE=false`, deploy migrations separately before starting
the service:

```sh
uv run alembic upgrade head
```

Startup fails if the schema is missing or outdated. `create_app(Settings(...))`
allows isolated application instances, including a separate database for each test.
Dependencies in `fure/api/dependencies.py` expose per-request sessions and resource
services, and a lifespan-owned execution service. No engine or session is created
at module import time.

## Schema

- `functions`: identity, name, description, active revision, flags, timestamps and
  an optimistic concurrency version. A partial unique index reserves names only
  for functions that have not been deleted.
- `revisions`: immutable function-owned implementation and runner snapshots,
  including previously inferred schemas. JSON snapshots contain a `type`
  discriminator. Credentials are persisted with runner settings and removed by
  API presenters before response serialization.
- `runs`: immutable revision reference, input/output, typed metadata, status and
  timestamps. Worker identity and heartbeat support cross-worker cancellation and
  recovery. Check constraints restrict statuses and reject negative durations.

Foreign keys preserve ownership and history. Timestamps are normalized to UTC on
database writes and reads, including timezone-naive values returned by SQLite.
JSON serialization rejects non-finite numbers. New runs and terminal transitions
use separate short transactions; expensive Python initialization and provider
requests do not hold database transactions.

## Layers

- Models and Alembic migrations define the relational schema.
- Mappers serialize snapshots and reconstruct domain objects using `restore`.
  Entity links retain identity; the trusted mapper wires the function/revision
  cycle without calling business setters.
- Repositories query and paginate domain entities. Function writes compare an
  optimistic version; execution transitions compare the expected status.
- Resource services enforce name conflicts, revision ownership, soft deletion and
  selection of the current revision. The execution service owns tasks, deadlines,
  cancellation, heartbeats and stale execution recovery.
- Routers validate requests, invoke injected services and present public DTOs.

Database state is authoritative across workers. A cancelled task cannot later
overwrite cancellation with a success or failure. Shutdown affects only runs owned
by that worker; active runs in another healthy process remain active. Abrupt worker
loss is detected after its heartbeat lease expires; executions are not retried
automatically because functions may have side effects.

## Tests

Run `uv run python -m unittest discover -s tests`. Integration tests use isolated
temporary SQLite files by default. To exercise the same API and repository tests
against PostgreSQL, set `FURE_TEST_DATABASE_URL` to a test server connection URL.
The account must be able to create databases. Every test creates a uniquely named
database and drops only that database during cleanup; the supplied database itself
is never cleared. LLM calls are mocked; no provider credentials or paid requests
are needed for the test suite.
