# Agents Guide

This guide tells you where the code is, what rules to follow, and how to run, debug, and test—for the core language/runner, the apps, and new workflows.

---

## 1) Working on the core (WIRL language + runner)

### Code map

- **DSL grammar + parser**: `packages/wirl-lang/wirl_lang/wirl.bnf`, `packages/wirl-lang/wirl_lang/wirl_parser.py` (public API: `parse_wirl_to_objects`)
- **Runner**: `packages/wirl-pregel-runner/` — CLI entry: `python -m wirl_pregel_runner.pregel_runner` and graph builder: `wirl_pregel_runner/pregel_graph_builder.py`
- **Example DSLs + tests**: `packages/wirl-pregel-runner/tests/` and `packages/wirl-pregel-runner/tests/wirls/`
- **VSCode syntax**: `extensions/vscode/` (grammar in `syntaxes/wirl.tmLanguage.json`)

### Rules to respect

- **Grammar change rule**: anything you add to the BNF must be reflected in the parser (transformer, dataclasses) so the AST supports it. Edit `wirl_parser.py` alongside `wirl.bnf`. Keep the AST stable for existing constructs (backward compatibility).
- **Runner wiring**: grammar changes are inert until the runner knows how to execute them. Extend `pregel_graph_builder.py` if the new syntax affects scheduling, dependencies, guards, reducers, etc.
- **VSCode extension**: update tokens/keywords in `extensions/vscode/syntaxes/wirl.tmLanguage.json` to keep highlighting in sync; re‑package the extension.

### WIRL language rules

When authoring or modifying `.wirl` workflows, follow these fundamental rules:

1. **Input and output parameters are mandatory**: Every workflow must declare `input` and `output` parameters. Workflows without both will not execute properly.

2. **First node must depend on an input parameter**: The first node to run must have a dependency on at least one of the workflow's input parameters. Without this dependency, the workflow will not start execution.

3. **Cycle node inputs are restricted**: Inside cycles, nodes can only use:
   - Inputs from neighboring nodes within the cycle
   - Inputs of the cycle itself

   Inputs from outside the cycle are not directly accessible and must be proxied through cycle input parameters to be available inside the cycle.

4. **Dotted notation inside cycles**: Inside a cycle, all input values must use dotted notation, even when referencing the cycle's own inputs. For example, if you're inside a cycle named `ProcessItems`, reference cycle inputs as `ProcessItems.cycleInput` rather than just `cycleInput`.

### Run, debug, test

#### Environment setup (repo root)

```bash
make workflows-setup          # .venv + core pkgs + per-workflow deps
make workflows-setup-dev      # same, dev‑editable installs
```

These targets install `wirl-lang` and `wirl-pregel-runner` editable and pick up all `workflow_definitions/**/requirements.txt`.

#### Unit tests (runner)

```bash
make -C packages/wirl-pregel-runner test
```

Example runner tests and example `.wirl` files live under `packages/wirl-pregel-runner/tests/…`. Mirror that pattern when you add new grammar/runner features.

#### Add a focused e2e test for a new syntax

1. Create a minimal `.wirl` in `packages/wirl-pregel-runner/tests/wirls/`.
2. Add a `tests/test_*.py` that calls `run_workflow` with mock functions and asserts node outputs / guard behavior.

#### Run a workflow from the repo root (no app involved)

```bash
make run-workflow \
  WORKFLOW=<dir-under-workflow_definitions> \
  FUNCS=workflow_definitions.<name>.<name> \
  PARAMS="key1=value1 key2=value2"
```

This wraps the CLI `python -m wirl_pregel_runner.pregel_runner`. Use it to sanity‑check grammar/runner changes quickly.

#### VSCode syntax package

```bash
cd extensions/vscode
npm install
npx vsce package   # then install generated .vsix in VS Code
```

### Make targets (core)

- **Root**: `workflows-setup`, `workflows-setup-dev`, `test-workflow`, `test-all-workflows`, `run-workflow`, `install-precommit`, `lint`
- **packages/wirl-lang**: `install`, `install-dev`, `lint`, `format`
- **packages/wirl-pregel-runner**: `test` (plus `lint`/`format`). Prefer the CLI shown above over the package's `make run` (the CLI path is authoritative).

---

## 2) Working on the apps (backend, workers, frontend)

### Architecture

- **Workers** are the only component that executes workflows. They poll the DB, claim a job, run WIRL via the runner, and update `workflow_runs`. See `apps/workers/workers/worker_pool.py`.
- **Backend** is a FastAPI API over the DB, not an executor. It exposes templates, run history, and run control endpoints; it writes rows for workers to pick up. Tables live under `apps/backend/backend/models.py` (`workflow_runs`).
- **Frontend** is a simple JS app served in dev via Overmind at <http://localhost:3000>.

### Code map (apps)

- **Backend**: `apps/backend/` (FastAPI app `backend/main.py`, SQLAlchemy models, Makefile). Docs at `/api/docs`.
- **Workers**: `apps/workers/` (async worker pool in `workers/worker_pool.py`, Makefile).
- **Frontend**: `apps/frontend/` (dev service started by Overmind).

### Run & test (apps)

#### Everything via Overmind (recommended for local dev)

```bash
# repo root
make workflows-setup
# set env (DB + workflows path)
# DATABASE_URL, WORKFLOW_DEFINITIONS_PATH (see below)
make run_wirl_apps      # or: overmind start -f procfile
```

Services: Backend <http://localhost:8000>, Frontend <http://localhost:3000>.

#### Backend only

```bash
# from apps/backend
make install
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workflows make run
# then open http://localhost:8000/api/docs
```

Endpoints: list templates, start/continue/cancel runs, inspect runs.

#### Workers only

```bash
# from apps/workers
make install
# ensure DATABASE_URL is set to a Postgres instance
make run
```

Logs are the primary debugging tool. Raise verbosity by changing the `logging.basicConfig(level=...)` line in `workers/worker_pool.py`.

#### Inspect worker process output under Overmind

```bash
overmind connect workers
# detach: Ctrl-b, then d
```

(Procfile wiring + Overmind conventions.)

#### DB + config required for apps

Create `.env` in the repo root (example):

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workflows
WORKFLOW_DEFINITIONS_PATH=/absolute/path/to/workflow_definitions
```

Use the provided macOS script to launch Postgres quickly if you don't have one running:

```bash
chmod +x scripts/macos/container-start-postgres.sh
./scripts/macos/container-start-postgres.sh
```

### Testing changes

- **Workers**: write tests that simulate job claiming and execution; prefer an ephemeral Postgres (container/script) for integration tests since workers use asyncpg. Use a Postgres or SQLite checkpointer as appropriate for your test setup (packages depend on both Postgres and SQLite checkpointers).
- **Backend**: add API tests for new endpoints/behaviors, then validate manually via `/api/docs`.
- **Frontend**: run in browser under Overmind and add/execute its tests via the app's own tooling (Overmind exposes port 3000).

### Make targets (apps)

- **Backend** (`apps/backend`): `install`, `install-dev`, `run`, `test`, `format`, `lint`
- **Workers** (`apps/workers`): `install`, `install-dev`, `run`, `test`, `format`, `lint`
- **Root helpers**: `run_wirl_apps` (Overmind), `install-backend-deps`, `install-worker-deps`, `install-frontend-deps`

---

## 3) Working on or creating new workflows

### Folder layout (one workflow per folder)

```text
workflow_definitions/<workflow_name>/
  <workflow_name>.wirl         # the DSL
  <workflow_name>.py           # pure functions called from the DSL
  requirements.txt             # only what this workflow needs
  tests/                       # at least one "happy path" test
  README.md                    # what it does, setup (ENV, inputs/outputs)
```

Per‑workflow requirements are installed by the root `workflows-setup` target.

### Function rules

- **Pure functions only**. No shared mutable state. Names must match call identifiers in the `.wirl`. Arguments in Python must match node inputs, plus a trailing `config: dict`.
- **Config** contains node `const { … }` merged with runner config; access `thread_id` at `config["configurable"]["thread_id"]`. Keep large prompts/helpers in separate modules.
- **Constants, secrets, inputs**
  - Put non‑PII constants in node `const { … }` (clear in VCS).
  - Use ENV for secrets/private data.
  - Pass truly dynamic values as workflow inputs.

  (Matches the example and runner patterns.)
- **LLMs**: default to local models; prefer LangChain/LangGraph plumbing unless specified otherwise. (Runner depends on LangGraph; integrate LLM calls inside your Python steps as needed.)

### Run & test workflows

#### Unit‑style, with mocks (recommended pattern)

```bash
make test-workflow WORKFLOW=<workflow_name>     # runs pytest with the runner transiently available
```

Your test should stub every node function, run the flow, and assert the final result and critical step outputs.

#### End‑to‑end run from CLI

```bash
make run-workflow \
  WORKFLOW=<workflow_name> \
  FUNCS=workflow_definitions.<workflow_name>.<workflow_name> \
  PARAMS="key1=value1 key2=value2"
```

This wraps `python -m wirl_pregel_runner.pregel_runner` ….

---

## Quick Overmind / ports / environment

- **Start all**: `make run_wirl_apps` → Backend at <http://localhost:8000>, Frontend at <http://localhost:3000>. Attach to workers: `overmind connect workers` (detach with Ctrl‑b, then d).
- **Required env**: `DATABASE_URL`, `WORKFLOW_DEFINITIONS_PATH` (set in `.env` at repo root).

---

## Appendix: Handy Make targets (root)

- `workflows-setup`, `workflows-setup-dev` — bootstrap `.venv` + installs.
- `test-workflow WORKFLOW=<name>` / `test-all-workflows`.
- `run-workflow WORKFLOW=<name> FUNCS=<module> PARAMS="k=v …"`.
- `run_wirl_apps` — Overmind all services via procfile.
- `install-precommit`, `lint`.
