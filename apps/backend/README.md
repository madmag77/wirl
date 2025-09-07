# WIRL Backend (FastAPI)

FastAPI service that exposes workflow templates, runs workflows, and serves history via a simple REST API. Ships with SQLAlchemy models and a minimal schema created at startup.

- **Docs**: available at `/api/docs`
- **Default port**: 8000 (Procfile) or 8008 when using the backend `Makefile`
- **Python**: 3.10+

## Contents
- [WIRL Backend (FastAPI)](#wirl-backend-fastapi)
  - [Contents](#contents)
  - [Quick start](#quick-start)
  - [Configuration](#configuration)
  - [Run locally](#run-locally)
  - [API](#api)
  - [Development](#development)

## Quick start

From the repo root, create a virtual environment with [uv](https://docs.astral.sh/uv/) and install packages used by the monorepo (recommended):

```bash
# From repo root
make workflows-setup      # creates .venv and installs core + workflow deps
```

Then start Postgres and the backend:

```bash
# Start Postgres (podman/docker via the provided helper)
./scripts/start-postgres.sh

# Start backend from this directory (apps/backend)
make run                   # uvicorn backend.main:app --host 0.0.0.0 --port 8008 --reload
```

Open: `http://localhost:8008/api/docs`

If you prefer the defaults used by the Procfile (port 8000), run uvicorn directly:

```bash
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## Configuration

Environment variables:
- **DATABASE_URL**: SQLAlchemy DB URL. Example: `postgresql://postgres:postgres@localhost:5432/workflows`
- **WORKFLOWS_DIR**: Path (relative to repo root) to search for `.wirl` templates. Default: `workflow_definitions`

Notes:
- On app startup, the DB schema for `workflow_runs` is created automatically.
- CORS is open by default for development.

## Run locally

Using the backend `Makefile` (this directory):

```bash
# Install backend package in editable mode
make install         # or: make install-dev

# Run the API on 0.0.0.0:8008
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workflows \
make run
```

## API

All endpoints return JSON. See live docs at `/api/docs` when the server is running.

- GET `/workflow-templates`
  - Returns all discovered `.wirl` templates. Response items: `{ id, name, path }`.

- GET `/workflows`
  - Returns workflow run history. Items: `{ id, template, status, created_at }`.

- GET `/workflows/{workflow_run_id}`
  - Returns details: `{ id, inputs, template, status, result, error }`.

- POST `/workflows`
  - Body: `{ "template_name": string, "inputs": object }`
  - Queues a new workflow run. Returns `{ id, status, result }`.

- POST `/workflows/{workflow_run_id}/continue`
  - Body: `{ "inputs": object }`
  - Continue a run that is waiting for input.

- POST `/workflows/{workflow_run_id}/cancel`
  - Cancels a running workflow.

Example (start a workflow):

```bash
curl -X POST http://localhost:8008/workflows \
  -H 'Content-Type: application/json' \
  -d '{"template_name":"sample","inputs":{"query":"Hello"}}'
```

## Development

Formatting and linting (ruff):

```bash
make format   # format + import order
make lint     # lint
```

Tests (if present):

```bash
make test
make test_cov
```