# WIRL — Explicit Workflows with Human Checkpoints

WIRL is a lightweight **DSL**, **runner**, and **set of apps** for automating routines with **deterministic, inspectable** workflow graphs. Workflows support **retries**, **branching**, **cycles**, and **Human‑in‑the‑Loop (HITL)** as first‑class concepts. LLMs are pluggable (local or hosted), while control‑flow remains fixed and auditable.

## When this is useful

1. You’re exploring ways to automate personal or work routines.
2. You like Python/LangGraph, but scaling beyond 1–2 ad‑hoc workflows became messy (state, reuse, approvals, retries).
3. You tried n8n/low‑code, but the visual model is heavy, hard for AI to modify, and versioning/custom code gets awkward.
4. You want reproducible research/AI pipelines with checkpoints and retries, without adopting a full MLOps stack.
5. You prefer workflow **descriptions** that are human‑readable and AI‑generatable, separated cleanly from infra and the runner.

## Quickstart

### Prerequisites

- Python **3.11+**
- uv (recommended) or pip
- Optional: an OpenAI‑compatible endpoint (e.g., **Ollama** locally or a hosted API)

### Install

``` bash
git clone https://github.com/madmag77/wirl
cd wirl
make workflows-setup
# creates .venv, installs local packages, and installs per-workflow requirements
```

### Run a workflow from the terminal

Use the provided Make target:

```bash
make run-workflow \
  WORKFLOW=<workflow_name> \
  FUNCS=workflow_definitions.<workflow_name>.<workflow_name> \
  PARAMS="key1=value1 key2=value2"
```

Example — **Paper rename**:

```bash
make run-workflow \
  WORKFLOW=paper_rename_workflow \
  FUNCS=workflow_definitions.paper_rename_workflow.paper_rename_workflow \
  PARAMS='drafts_folder_path="/Users/username/Library/Mobile Documents/com~apple~CloudDocs/papers_unsorted" processed_folder_path="/Users/username/Library/Mobile Documents/com~apple~CloudDocs/papers_sorted"'
```

If you already have **Ollama** installed or plan to use a commercial LLM API, you can run most workflows immediately.

### Start the apps/platform (optional but recommended for HITL + observability)

To run regularly, see run history, and perform approvals, bring up the backend and frontend:
1. Provision **Postgres** (Docker, a local install, or a free Supabase instance). For Mac (latest versoin only) users there is a script at `scripts/container-start-postgres.sh` that sets up the container with postgres for you.
2. Export the Postgres connection environment variables required by the backend (e.g., DATABASE_URL, for local setup it's `postgresql://postgres:postgres@localhost:5432/workflows`).
3. Set environment variable `WORKFLOW_DEFINITIONS_PATH` to the absolute path to workflow definitions. Like this:
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workflows
WORKFLOW_DEFINITIONS_PATH=/Users/username/wirl/workflow_definitions
```
4. Start the apps:
``` bash
make run_wirl_apps   # or: overmind start
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

With the apps running you can **start, continue, retry**, and provide **HITL inputs** from the UI. The runs list now supports **paging**, and each run exposes **View Run Details** to inspect every step’s inputs and outputs.

### Autostart on macOS

To run the apps automatically after reboot:

```bash
scripts/macos/mac-install-launchctl.sh
```

#### Viewing launchctl logs

When running via launchctl, logs are stored in `~/.local/log/`:

```bash
# View live output logs
tail -f ~/.local/log/wirl-workflows-overmind.out

# View live error logs
tail -f ~/.local/log/wirl-workflows-overmind.err

# View both logs simultaneously
tail -f ~/.local/log/wirl-workflows-overmind.{out,err}

# Check service status
launchctl list | grep com.local.wirl.overmind

# Connect to individual processes via Overmind
overmind connect backend -s ~/.overmind.sock
overmind connect workers -s ~/.overmind.sock
# Detach with: Ctrl-b, then d

# Restart the service
launchctl unload ~/Library/LaunchAgents/com.local.wirl.overmind.plist
launchctl load ~/Library/LaunchAgents/com.local.wirl.overmind.plist
```

#### Troubleshooting launchctl services on macOS

**Note:** The install script (`scripts/macos/mac-install-launchctl.sh`) now automatically:
- Loads `DATABASE_URL` and `WORKFLOW_DEFINITIONS_PATH` from `.env` file and adds them to the plist
- Cleans up stale socket files before starting the service
- Provides detailed debugging output after installation

If the WIRL services aren't running properly via launchctl, use these debugging commands:

**Check if services are running:**
```bash
# List all WIRL-related services
launchctl list | grep -i wirl

# Output format: PID  EXIT_CODE  SERVICE_NAME
# - PID: Process ID if running, "-" if not running
# - EXIT_CODE: 0 = success, 1+ = error
# Example output:
#   -       1       com.local.wirl.overmind  <- Service crashed (exit code 1)
#   2309    0       com.apple.container...   <- Service running (PID 2309)
```

**Get detailed service status:**
```bash
# Detailed info about the service
launchctl print gui/$(id -u)/com.local.wirl.overmind

# Shows: state, runs count, last exit code, log paths, environment variables
```

**Check recent logs:**
```bash
# View last 50 lines of error log (most useful for debugging)
tail -50 ~/.local/log/wirl-workflows-overmind.err

# View last 50 lines of output log
tail -50 ~/.local/log/wirl-workflows-overmind.out

# Follow logs in real-time
tail -f ~/.local/log/wirl-workflows-overmind.{out,err}
```

**Common issues and solutions:**

1. **Stale socket file (service exits with code 1):**
   - **Symptom:** Error log shows "it looks like Overmind is already running"
   - **Solution:** The plist template now auto-cleans stale socket files. If you installed before this fix, manually remove:
   ```bash
   rm -f ~/path/to/wirl/.overmind.sock
   # Service will auto-restart after cleanup
   ```
   - **Note:** If you modified the plist template before this fix, reinstall with:
   ```bash
   scripts/macos/mac-install-launchctl.sh
   ```

2. **Missing environment variables:**
   - **Symptom:** Backend or workers crash immediately after starting
   - **Cause:** Required environment variables (`DATABASE_URL`, `WORKFLOW_DEFINITIONS_PATH`) are not set
   - **Solution:**
     1. Create a `.env` file in the repo root with required variables:
     ```bash
     DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workflows
     WORKFLOW_DEFINITIONS_PATH=/absolute/path/to/wirl/workflow_definitions
     ```
     2. Reinstall the service (it will automatically pick up the `.env` file):
     ```bash
     scripts/macos/mac-install-launchctl.sh
     ```
     3. Verify environment variables were added:
     ```bash
     launchctl print gui/$(id -u)/com.local.wirl.overmind | grep -A 20 "environment ="
     ```

3. **Service not loaded at all:**
   - **Symptom:** `launchctl list | grep wirl` returns nothing
   - **Solution:** Reinstall the service:
   ```bash
   scripts/macos/mac-install-launchctl.sh
   ```

4. **Service continuously restarting (high runs count):**
   - **Symptom:** `launchctl print` shows "runs = 49+" with exit code 1
   - **Solution:** Check error logs to identify the root cause:
   ```bash
   tail -100 ~/.local/log/wirl-workflows-overmind.err
   ```

5. **All services exit immediately after starting:**
   - **Symptom:** Output log shows services starting then immediately "Interrupting..." and "Exited with code 0"
   - **Cause:** Procfile contains a short-lived process that exits immediately (e.g., a command that just checks status and exits)
   - **Solution:** All processes in the procfile must be long-running. If you need initialization, combine it with a long-running command:
   ```bash
   # Bad: exits immediately
   container: sh -c 'container system start'

   # Good: initialization followed by long-running command
   postgres: sh -c 'container system start; container start postgres; container logs -f postgres'
   ```
   - **Why:** Overmind interprets any process exit as a signal to shut down all services. Keep processes alive with `-f` flags, `tail -f`, `sleep infinity`, or similar.

**Check running services (once overmind is up):**
```bash
# Check status of all services managed by overmind
overmind status -s /path/to/repo/.overmind.sock

# Example output:
# PROCESS   PID       STATUS
# postgres  11639     running
# backend   11640     running
# workers   11641     running
# frontend  11642     running

# Connect to a specific service (to see its live output)
overmind connect workers -s /path/to/repo/.overmind.sock
# Press Ctrl-b then d to detach
```

**Manual service control:**
```bash
# Unload (stop) the service
launchctl unload ~/Library/LaunchAgents/com.local.wirl.overmind.plist

# Load (start) the service
launchctl load ~/Library/LaunchAgents/com.local.wirl.overmind.plist

# Or use the bootstrap/bootout commands (newer macOS)
launchctl bootout gui/$(id -u)/com.local.wirl.overmind
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.local.wirl.overmind.plist
```

**Verify overmind works manually:**
```bash
cd ~/path/to/wirl
overmind start  # Should start all services without errors
# Press Ctrl-C to stop when testing
```

If overmind works manually but fails via launchctl, the issue is likely environment-related (PATH, env vars, working directory).

### Schedule runs (optional)

WIRL now ships with a **built-in cron-style scheduler** so you can run workflows on a cadence without deploying extra services:

1. You can find Scheduled Triggers panel on the main page above the workflow runs history.
2. Click **Schedule Workflow** to define a name, pick a workflow template, provide JSON inputs, and enter a cron expression + timezone.
3. Toggle the trigger on. The backend persists it to Postgres and shows the next run time.

The FastAPI backend hosts a lightweight scheduler that polls the `workflow_triggers` table and enqueues runs whenever a trigger is due. The worker service picks up the queued run just like any manual execution, so no additional infrastructure is required. You can pause/resume triggers from the UI; invalid templates or cron expressions automatically disable the trigger and surface the error message inline.

![Schedule a task](images/schedule.png?raw=true "Schedule a task")

If you prefer external schedulers, you can still wire GitHub Actions (see `infra/github_actions_document_sort.yaml`) or any other job runner against the public API.

## UI at a glance

- **Runs list** with paging. ![runs list](images/main.png?raw=true "Runs list")
- **View Run Details** for a single run: step timeline, status, retry count, and captured **inputs/outputs** per node. ![run details](images/run_details.png?raw=true "Run's details")
- **HITL** page to approve or edit at workflow checkpoints, then resume execution.![hitl](images/hitl.png?raw=true "HITL")

## Examples

There are four example workflows (three are used daily):

1. **Paper rename**
    You save papers to papers_unsorted with unreadable names (e.g., 2411.06037v3.pdf). This workflow reads new PDFs, uses a **vision‑capable model** via an OpenAI‑compatible endpoint (e.g., Ollama) to extract **title/author/year** from the first pages, and saves the file with a proper name in papers_sorted. You only consult the sorted folder.
2. **News digest**
    You provide sources. Each morning the workflow checks for new posts since the last run, summarizes them with a local LLM, and emails a digest with links. You read the digest and open only what matters.
3. **Photo → notes (HITL)**
    Many people snap photos/screenshots instead of writing notes (announcements, tracking numbers, invoices). The workflow collects yesterday’s images from a designated folder (Automator/Shortcuts can assist on macOS to fill this folder with your last photos), extracts useful info with a vision model, and emails you a report plus a link to the local **HITL** page. You open a link and write simple instructions (“keep only the tracking number with a description”, “make a note from this invoice”), and the workflow applies them and writes the final note to **Obsidian** or any `md` based note-taking system.
4. **AutoRater evaluation (new)**
    A reproducible evaluation pipeline inspired by Google’s “autorater” idea: sample items (e.g., from **HotpotQA**), run **model‑as‑judge** prompts to assess whether context is sufficient prior to answering, aggregate metrics, and export a report. Extend with multiple rater models and a reduce step to compare systems.

## Developers’ section

### What you get

- **DSL**: A compact, readable language to declare nodes, edges, typed IO, when branches, cycle{... guard ...} loops, and **hitl{...}** checkpoints.
- **Runner**: Pregel‑style execution with **checkpointing**, **retries**, **resume**, and **HITL** pause/resume built in.
- **Apps**: Backend + workers + frontend for approvals and observability

### Repository layout (high level)
```
packages/
  wirl-lang/             # DSL grammar + parser
  wirl-pregel-runner/    # Pregel-style runner, checkpoints, HITL
workflow_definitions/
  paper_rename_workflow/
  ...
extensions/vscode/       # syntax highlighting for VS Code/Cursor
apps/                    # frontend + workers + backend (HITL + runs UI)
scripts/                 # setup/launch helpers
infra/                   # macOS launchctl, CI examples, etc.
```

### Authoring model

- **Separate the plan from the code.**
  - The **graph** lives in a .wirl file. This is the "plan": nodes, edges, branches, cycles, guards, and HITL.
  - The **logic** lives in **pure Python** functions that match each node's call target.
- **LLM‑friendly flow.**
    1. Use Cursor/Windsurf to generate the .wirl graph from a natural‑language description. There is a very detailed `Agents.md` file to help LLMs do it with good quality.
    2. Generate the Python module with node functions (pure, testable).
    3. Review the .wirl diff to verify control‑flow instantly.
- **Deterministic control‑flow.**
    Models can be stochastic; the **graph is not**. Guards and cycle limits are explicit and reviewable.

### WIRL language rules

When authoring `.wirl` workflows, follow these fundamental rules:

1. **Input and output parameters are mandatory**: Every workflow must declare `input` and `output` parameters. Workflows without both will not execute properly.

2. **First node must depend on an input parameter**: The first node to run must have a dependency on at least one of the workflow's input parameters. Without this dependency, the workflow will not start execution.

3. **Cycle node inputs are restricted**: Inside cycles, nodes can only use:
   - Inputs from neighboring nodes within the cycle
   - Inputs of the cycle itself

   Inputs from outside the cycle are not directly accessible and must be proxied through cycle input parameters to be available inside the cycle.

4. **Dotted notation inside cycles**: Inside a cycle, all input values must use dotted notation, even when referencing the cycle's own inputs. For example, if you're inside a cycle named `ProcessItems`, reference cycle inputs as `ProcessItems.cycleInput` rather than just `cycleInput`.

### **Writing node functions (pattern)**

- Keep functions **pure** and **idempotent** where possible.
- Use simple, typed inputs/outputs.
- Avoid hidden globals and side effects besides intentional outputs.

``` python
# workflow_definitions/your_flow/steps.py
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class PhotoInfo:
    path: str

def get_photos(folder: str, days_back: int) -> List[PhotoInfo]:
    ...

def extract_note(image_b64: str) -> str:
    ...

def append_and_check(notes: List[str], note: str, remaining: List[PhotoInfo]) -> Tuple[List[str], bool]:
    # returns (updated_notes, is_done)
    ...
```

### **Running a workflow (CLI)**

``` bash
python -m wirl_pregel_runner.pregel_runner \
  workflow_definitions/<name>/<name>.wirl \
  --functions workflow_definitions.<name>.<module> \
  --param key=value --param other=val
```

Or via Make:

``` bash
make run-workflow \
  WORKFLOW=<name> \
  FUNCS=workflow_definitions.<name>.<module> \
  PARAMS="key1=value1 key2=value2"
```

### **Observability**

- **Runs list** (paged).
- **Run details** with **inputs/outputs per node**, timestamps, durations, retry counts.
- **Checkpoints** at every node allow precise **resume** and **retry**.

### **Workflow triggers & scheduler**

- **Data model**: persisted in Postgres via `workflow_triggers` (see `apps/backend/backend/models.py`).
- **API**: CRUD endpoints under `/workflow-triggers` in `apps/backend/backend/main.py` expose trigger management to the UI.
- **Scheduler**: `apps/backend/backend/scheduler.py` runs inside the FastAPI process, polling for due triggers and enqueueing runs.
- **Duplicate protection**: the scheduler locks each due trigger row with `SELECT ... FOR UPDATE SKIP LOCKED`, refreshes `next_run_at`,
  and aligns cron evaluation to the prior fire time so the same trigger cannot be enqueued twice within the same minute even if multiple
  pollers overlap.
- **UI**: React components in `apps/frontend/src/components/WorkflowTriggersTable.jsx` allow creating, editing, pausing, and deleting triggers alongside manual runs.
- **Workers**: no change required; they keep polling the `workflow_runs` queue and execute runs spawned by triggers.

### **HITL (Human‑in‑the‑Loop)**

- Declare a checkpoint with hitl { correlation: "...", timeout: "..." }. Those parameters are not being used and preserved for future implementation.
- The runner pauses and persists state.
- Approvers act in the UI; the run resumes from the checkpoint with the decision recorded.

### **Configuration**

- **LLM endpoints**: Any OpenAI‑compatible base URL/key (Ollama locally or hosted APIs).
- **Database**: Postgres for run metadata and checkpoints (set DATABASE_URL or the backend’s required env vars).
- **Secrets**: Provide via env vars; swap for your secret manager as needed.
- **Scheduling**: use the built-in cron runner (FastAPI `backend/scheduler.py`, UI in `apps/frontend/src/components/WorkflowTriggersTable.jsx`) or wire any external system such as LaunchAgents/systemd, containers, or GitHub Actions (see infra/).

### **Adding a new workflow**

1. Create workflow_definitions/<your_workflow>/.
2. Add <your_workflow>.wirl (graph) and <your_workflow>.py (node functions).
3. (Optional) Add requirements.txt scoped to this workflow.
4. Run:
```bash
make run-workflow \
  WORKFLOW=<your_workflow> \
  FUNCS=workflow_definitions.<your_workflow>.<your_workflow> \
  PARAMS="..."
```
5. Inspect in the UI, use **View Run Details**, iterate.

### **Development tips**

- Keep node IO **simple, serializable**, and **explicit**.
- Reuse functions across workflows; treat .wirl files as the configuration surface.
- Favor **guarded loops** over unbounded iteration.
- Capture enough per‑node IO to debug, but redact sensitive fields when needed.

## What doesn't work and yet to be fixed
- Types in workflows are not being used now, they are only for you and LLM to understand the workflow better
- Cycles are only sequential for now, there is a plan to introduce parallel execution at scale
- Parameters in HITL block (correlation and timeout) are not being used
- There are no first class concept "retry" implemented yet (ideally you should be able to mark any node as retryable with parameters)

## **License**
MIT.
