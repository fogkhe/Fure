# Fure Workspace

A Nuxt 4 / Nuxt UI 4 interface based on the Nuxt UI Starter Template,
with an orange accent, Public Sans typography and light/dark themes.

The interface supports English (the default) and Russian. The language selector
is at the bottom left of the footer. A `fure_locale` cookie remembers the choice
for one year and is read during server rendering, including login redirects.
The browser's language does not override the default or the saved preference.
Page URLs remain the same in both languages.

Translations live in `i18n/locales/en.json` and `i18n/locales/ru.json`, using
`@nuxtjs/i18n`; Nuxt UI follows the active locale. Dates, duration, counts,
permissions and known API error messages are localized. Function names and
descriptions, implementation source/templates, schemas, results and raw run
metadata remain user data and are displayed as stored.

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
- Execution with schema-based fields or a JSON editor, output, duration and token counts; the Run button
  becomes Cancel while the user's execution is active and cancellable.
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
In manual mode, add each optional reasoning end marker as a separate list item.
Input fields support strings, numbers, booleans, enums, nested objects and arrays,
including local schema references and nullable values. Optional fields can be
omitted from the request. Switching editors preserves values and unknown keys;
unsupported schema constructs use JSON editing. Final schema validation is
performed by the backend.
The API never returns stored provider API keys: provide a key again when copying a
Jinja revision if the provider requires authentication.

With history access, the workspace submits to `/v1/functions/{id}/run?wait=false`
and polls the returned run ID. Cancel uses the same endpoint and confirmation as
history cancellation; it requires permission to cancel the user's own runs.
Closing the execution page stops polling and leaves execution running. The
history remains available for subsequent cancellation. Users without history
access use the synchronous execution mode.

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
