# Fure
A Function Runtime Environment

The [REST API contract](docs/api.md) covers functions, immutable revisions,
execution history and synchronous execution by function name.
Interactive documentation is available at `/docs` when the service is running.

SQLite is used by default; PostgreSQL is configured through `DATABASE_URL`.
Migrations, execution tasks and database resources are managed by the application
[lifespan](docs/storage.md). Run `uv run uvicorn fure.api:app --reload` to start.

The [Nuxt UI workspace](frontend/README.md) provides function management,
revision editing, execution and run history. Start it in a second terminal:

```sh
cd frontend
npm install
npm run dev
```

The frontend proxies API requests to `http://127.0.0.1:8000` by default.
Set `NUXT_API_BASE` in `frontend/.env` to use a different backend address.

## Docker Compose

From the repository root:

```sh
docker compose up --build -d --wait
```

- Workspace: http://localhost:3000
- API documentation: http://localhost:8000/docs

Compose starts PostgreSQL, applies database migrations during API startup, then
starts the production Nuxt server. Each service waits for its dependency to pass
its health check. The Nuxt proxy connects to `http://app:8000` inside the Docker
network; browser requests use the frontend address, without CORS configuration.
The production frontend image contains only the built Nuxt server and assets.

Create the first administrator, then sign in to the workspace:

```sh
docker compose exec app python -m fure.cli create-admin admin
```

The command prompts for a password (12–256 characters) and works only before the
first user exists. For local development use `uv run python -m fure.cli create-admin admin`.
Create subsequent users and roles in the interface. There is no public registration.
Existing functions become private after migration; previous history is retained
and is available to administrators.

PostgreSQL data is kept in the `database_data` named volume; runtime files are
kept in `app_data`. `docker compose down` stops the stack and preserves both.
Use `docker compose logs -f` to view logs.

To change the published ports, set `FRONTEND_PORT` and `API_PORT` in the root
`.env` file (defaults: 3000 and 8000). Compose supplies the internal database URL
and Nuxt API address directly; the local-development `DATABASE_URL` and
`frontend/.env` are not used by the containers.

When serving the workspace over HTTPS, set `SESSION_COOKIE_SECURE=true` in the
root `.env` and recreate the app container. Authentication, API-key scopes,
public execution and manual JSON extraction are described in [access control](docs/auth.md).
