# Fure Workspace

A Nuxt 4 / Nuxt UI 4 interface based on the Nuxt UI Starter Template,
with its green accent, Public Sans typography and light/dark themes.

## Development

Start FastAPI from the repository root:

```sh
uv run uvicorn fure.api:app --reload
```

In another terminal:

```sh
cd frontend
npm install
npm run dev
```

Open the address printed by Nuxt (http://localhost:3000 by default).
Use npm; package-lock.json pins the dependencies.
Create the first administrator with `uv run python -m fure.cli create-admin admin`
from the repository root, then log in. The account screen manages API keys and
password changes; administrators can create users and roles.

The Nuxt server connects to http://127.0.0.1:8000 by default.
Copy .env.example to .env and set NUXT_API_BASE to change that address.
The browser uses same-origin /api/* requests; the server forwards them to
FastAPI, so local development does not require CORS configuration.

## Features

- Functions: creation, exact-name search, status filters and pagination.
- Immutable Python/Inline and Jinja/OpenAI revisions: creation, cloning,
  source/schema inspection and selection of the current revision.
- Synchronous execution with JSON input, output, duration and token counts.
- Global, per-function and per-revision history with polling and pagination.
- Run details with input/output, errors, metadata and cancellation.
- Function settings, soft deletion and restoration with preserved history.
- Login/logout, role-aware navigation and controls, scoped API-key management.
- Administrator pages for users and roles; public execution settings for functions.

Creating a function opens its first revision editor. A new revision becomes
current by default; uncheck the corresponding option to save it without
selecting it. Python schemas come from type annotations. Jinja input schemas
come from templates; output schemas are entered as JSON. An empty output
schema {} requests text; with a nonempty schema, the Structured Outputs switch
chooses provider enforcement or manual JSON extraction and schema validation.
Manual mode supports optional reasoning end markers, one per line.
The API never returns stored provider API keys: provide a key again when copying a
Jinja revision if the provider requires authentication.

Closing the execution page does not cancel server-side work. Use run history
to cancel an active run. The execution request is synchronous: the X-Run-Id
header becomes available when the response arrives.

## Checks and production

```sh
npm run lint
npm run typecheck
npm run build
npm run preview
```

Start the production server with node .output/server/index.mjs.
Set NUXT_API_BASE to the FastAPI address reachable from the Nuxt server,
and optionally PORT. Start the backend and frontend separately.

To build and start the frontend, API and PostgreSQL together, run
`docker compose up --build -d --wait` from the repository root.
The workspace is available at http://localhost:3000. See the root README for
port configuration and persistent volumes.

## Browser tests

Prepare the backend environment with `uv sync` from the repository root.
Then, from `frontend`:

```sh
npx playwright install chromium
npm run build
npm run test:e2e
```

To use an already installed Chrome instead of downloading Chromium,
set `E2E_BROWSER_CHANNEL=chrome` (PowerShell: `$env:E2E_BROWSER_CHANNEL='chrome'`).
Tests start their own FastAPI and production Nuxt servers on ports 8011 and 3011.
Each run uses a fresh SQLite database under the ignored `.data/` directory.
The test fixture creates its own administrator; no production accounts are used.
No external LLM requests or real provider credentials are needed.
Failure traces and screenshots are saved under `test-results/`.
