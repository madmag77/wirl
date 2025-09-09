# WIRL — Workflow DSL and Runner

WIRL is a compact workflow DSL that compiles to an explicit directed graph (nodes, cycles with guards, reducers) and a Python runner that executes those graphs on a Pregel-like model.

This repository contains:
- DSL grammar and parser (`packages/wirl-lang`)
- Pregel-based runner (`packages/wirl-pregel-runner`)
- Example workflows (`workflow_definitions/`)
- Dev tooling (Procfile, VSCode syntax extension, macOS launchctl template)

## Repo structure
- `packages/wirl-lang/` — DSL grammar (`wirl.bnf`) and parser. See `packages/wirl-lang/README.md`.
- `packages/wirl-pregel-runner/` — Runner on top of LangGraph Pregel. See `packages/wirl-pregel-runner/README.md`.
- `workflow_definitions/` — Example and real workflows; each workflow keeps its Python step code and its own `requirements.txt`.
- `extensions/vscode/` — VSCode extension for `.wirl` syntax highlighting.
- `apps/` — Backend/frontends (placeholders for now).
- `infra/macos/` — macOS `launchctl` template.
- `scripts/` — Helper scripts (mac install, docker, postgres).

## Prerequisites
- Python 3.11+
- uv package manager (`pip install uv` or see docs)
- macOS users for PDF workflows: Poppler (`brew install poppler`) for `pdf2image`

Optional (for process supervision/local services):
- Overmind (`brew install overmind`)

## Quick start
Install local packages and per-workflow dependencies into a repo-local virtualenv.

```bash
make workflows-setup
```
What it does:
- Creates `.venv/` via `uv venv`
- Installs local packages editable: `packages/wirl-lang`, `packages/wirl-pregel-runner`
- Finds all `workflow_definitions/**/requirements.txt` and installs them into `.venv`
- Leaves placeholders for backend/workers deps

If you prefer manual steps:
```bash
uv venv .venv
uv pip install --python .venv/bin/python -e packages/wirl-lang
uv pip install --python .venv/bin/python -e packages/wirl-pregel-runner
# install per-workflow deps
find workflow_definitions -type f -name requirements.txt -print0 | \
  xargs -0 -I {} uv pip install --python .venv/bin/python -r {}
```

## Run an example workflow
The example `PaperRenameWorkflow` reads the first pages of PDFs, extracts metadata with a VLM, and renames the files.

Requirements:
- Poppler installed: `brew install poppler`
- A local or remote OpenAI-compatible endpoint (e.g., Ollama with OpenAI API, OpenRouter, etc.) — the example uses a base URL like `http://localhost:11434/v1/` and a placeholder API key.

Command:
```bash
. .venv/bin/activate
python -m wirl_pregel_runner.pregel_runner \
  workflow_definitions/paper_rename_workflow/paper_rename_workflow.wirl \
  --functions workflow_definitions.paper_rename_workflow.paper_rename_workflow \
  --param drafts_folder_path=/absolute/path/to/drafts \
  --param processed_folder_path=/absolute/path/to/processed
```
Notes:
- The functions module (`--functions`) is the Python file that implements the `call` targets in the `.wirl`.
- For the VLM, set your base URL/model in the workflow constants or code, and ensure an API key if required.

## Per-workflow dependencies
Each workflow can declare its own Python requirements in a `requirements.txt` placed next to its `.wirl` and step code. Example:
```
workflow_definitions/<workflow_name>/
  <workflow_name>.wirl
  <workflow_name>.py
  requirements.txt
```
- The Makefile target installs all such requirements into `.venv`.
- You can pin per-workflow versions without impacting other workflows.
- Optionally maintain a repo-level `constraints.txt` and pass `-c constraints.txt` if you prefer central pinning.

## Running on macOS

### Option 1: Manual with Overmind (Development)
Run all apps locally using overmind and the included `Procfile`:

```bash
# Install overmind
brew install overmind

# Start all services (postgres, backend, workers, frontend)
overmind start
```

Services will run on:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Postgres: via Docker container

### Option 2: Auto-start Service (Production)
Install as a macOS LaunchAgent service that starts automatically on boot:

```bash
# One-command installation
chmod +x scripts/macos/mac-install-launchctl.sh
./scripts/macos/mac-install-launchctl.sh
```

This script will:
- Install overmind (if missing)
- Generate plist from template with your system paths
- Install and load the LaunchAgent service
- Verify everything is running

**Service Management:**
```bash
# Check status
launchctl list | grep com.local.wirl.overmind

# View logs
tail -f ~/.local/log/wirl-workflows-overmind.out

# Uninstall service
./scripts/macos/mac-install-launchctl.sh --uninstall
```

## Development
- DSL and parser: see `packages/wirl-lang/README.md` for API (`parse_wirl_to_objects`) and grammar notes.
- Runner: see `packages/wirl-pregel-runner/README.md` for API and CLI usage.
- VSCode syntax: `extensions/vscode/README.md` for packaging and local install.

## Creating your workflows

1) Create a new workflow folder and three files

```
workflow_definitions/<workflow_name>/
  <workflow_name>.wirl            # DSL definition
  <workflow_name>.py              # Python implementation of functions referenced in the DSL
  requirements.txt                # Workflow-specific dependencies (only what this workflow needs)
```

2) Write tests for your workflow

- Place tests under `workflow_definitions/<workflow_name>/tests/`.
- Start by testing the DSL in isolation using the runner with stubbed functions, mirroring the pattern from `packages/wirl-pregel-runner/tests/test_wirl_with_cycles_runner.py`.
- Example command (no permanent dependency; uses a transient runner install):

```bash
uv run --with ./packages/wirl-pregel-runner -- pytest workflow_definitions/<workflow_name>/tests -q
```

- You can also use the Makefile shortcut from the repo root:

```bash
make test-workflow WORKFLOW=<workflow_name>  # adds runner transiently and runs pytest
```

3) Implement and unit-test Python functions

- Implement the functions referenced by `call` statements in `<workflow_name>.py`.
- Unit-test those Python functions directly (pure pytest) without the runner where it makes sense.

4) Run the workflow end-to-end

- Use the provided Makefile target to run a workflow from its DSL file, pointing to your Python functions module and passing input params:

```bash
make run-workflow \
  WORKFLOW=<workflow_name> \
  FUNCS=workflow_definitions.<workflow_name>.<workflow_name> \
  PARAMS="key1=value1 key2=value2"
```

Notes:
- `WORKFLOW` is the directory name under `workflow_definitions/`.
- `FUNCS` is the import path to the module exposing the functions used in the `.wirl` file.
- `PARAMS` is optional; specify space-separated key=value pairs that match your workflow inputs.

## License
MIT — see `LICENSE` at the repo root.
