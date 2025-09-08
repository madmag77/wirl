# AI Agent Developer Notes for WIRL Repository

This document provides comprehensive guidance for AI agents working with developers on the WIRL (Workflow DSL and Runner) repository.

## What is WIRL?

WIRL is a compact workflow DSL (Domain Specific Language) that compiles to an explicit directed graph with nodes, cycles with guards, and reducers. It includes a Python runner that executes these graphs on a Pregel-like model.

**Core Components:**
- **DSL Grammar & Parser** (`packages/wirl-lang/`) - Parses `.wirl` files using BNF grammar
- **Pregel Runner** (`packages/wirl-pregel-runner/`) - Executes workflows using LangGraph Pregel
- **Workflow Definitions** (`workflow_definitions/`) - Example workflows with Python implementations
- **Development Tools** - VSCode syntax extension, macOS launchctl template, Procfile for local dev

## Repository Structure

```
/Users/artemgoncharov/wirl/
├── packages/
│   ├── wirl-lang/           # DSL grammar (wirl.bnf) and parser
│   └── wirl-pregel-runner/  # LangGraph Pregel-based runner
├── workflow_definitions/    # Workflow examples and implementations
│   └── paper_rename_workflow/
│       ├── paper_rename_workflow.wirl  # DSL definition
│       ├── paper_rename_workflow.py    # Python implementation
│       └── requirements.txt            # Workflow-specific dependencies
├── apps/
│   ├── backend/            # FastAPI backend (placeholder)
│   ├── frontend/           # React frontend (placeholder)  
│   └── workers/            # Background workers (placeholder)
├── extensions/vscode/      # VSCode syntax highlighting extension
├── infra/macos/           # macOS LaunchAgent template
├── scripts/macos/         # Installation and setup scripts
└── procfile               # Overmind process definition
```

## How to Use WIRL

### Prerequisites
- **Python 3.11+** 
- **uv package manager** (`pip install uv`)
- **macOS users**: Poppler for PDF workflows (`brew install poppler`)
- **Optional**: Overmind for process supervision (`brew install overmind`)

### Quick Setup
```bash
# Install all dependencies (recommended)
make workflows-setup

# Manual setup (alternative)
uv venv .venv
uv pip install --python .venv/bin/python -e packages/wirl-lang
uv pip install --python .venv/bin/python -e packages/wirl-pregel-runner
find workflow_definitions -type f -name requirements.txt -print0 | \
  xargs -0 -I {} uv pip install --python .venv/bin/python -r {}
```

### Running a Workflow
```bash
. .venv/bin/activate
python -m wirl_pregel_runner.pregel_runner \
  workflow_definitions/paper_rename_workflow/paper_rename_workflow.wirl \
  --functions workflow_definitions.paper_rename_workflow.paper_rename_workflow \
  --param drafts_folder_path=/absolute/path/to/drafts \
  --param processed_folder_path=/absolute/path/to/processed
```

## How to Install Locally on macOS

### Option 1: Development Setup (Manual with Overmind)
```bash
# Install overmind
brew install overmind

# Start all services using Procfile
overmind start
```

**Services run on:**
- Frontend: http://localhost:3000
- Backend: http://localhost:8000  
- Postgres: Docker container

### Option 2: Production Setup (Auto-start Service)

**Step 1: LaunchCtl Template → Plist**
The system uses a template (`infra/macos/launchctl.plist.template`) that gets converted to a proper plist file with system-specific paths.

**Step 2: Check Overmind Installation**
The installation script automatically checks for and installs overmind if missing.

**Step 3: Run Installation Script**
```bash
chmod +x scripts/macos/mac-install-launchctl.sh
./scripts/macos/mac-install-launchctl.sh
```

**Step 4: Check Everything Running**
```bash
# Check service status
launchctl list | grep com.local.wirl.overmind

# Check overmind socket
ls -la .overmind.sock
```

**Step 5: Debug Errors**
If issues occur:
```bash
# View output logs
tail -f ~/.local/log/bpmn-workflows-overmind.out

# View error logs  
tail -f ~/.local/log/bpmn-workflows-overmind.err

# Restart service
launchctl unload ~/Library/LaunchAgents/com.local.wirl.overmind.plist
launchctl load ~/Library/LaunchAgents/com.local.wirl.overmind.plist

# Test overmind manually
cd /Users/artemgoncharov/wirl && overmind start

# Uninstall service
./scripts/macos/mac-install-launchctl.sh --uninstall
```

## How to Develop

### Developing New Workflows

**Structure:** Each workflow needs its own folder with three files:
```
workflow_definitions/my_new_workflow/
├── my_new_workflow.wirl      # DSL definition
├── my_new_workflow.py        # Python implementation
└── requirements.txt          # Dependencies
```

**WIRL DSL Example:**
```wirl
workflow MyWorkflow {
  metadata {
    description: "My custom workflow"
    owner: "developer"
    version: "1.0"
  }
  
  inputs {
    String input_param
  }
  
  outputs {
    String result = ProcessData.output
  }
  
  node ProcessData {
    call process_data_function
    inputs {
      String data = input_param
    }
    outputs {
      String output
    }
  }
}
```

**Python Implementation Pattern:**
```python
def process_data_function(data: str, config: dict) -> dict:
    # Process the data
    result = f"Processed: {data}"
    return {"output": result}
```

### How to Test

**Unit Testing:**
- Test individual Python functions in workflow implementations
- Test DSL parsing: `packages/wirl-lang/` contains parser tests
- Test runner: `packages/wirl-pregel-runner/tests/` contains runner tests

**Integration Testing:**
```bash
# Test workflow end-to-end
. .venv/bin/activate
python -m wirl_pregel_runner.pregel_runner \
  workflow_definitions/your_workflow/your_workflow.wirl \
  --functions workflow_definitions.your_workflow.your_workflow \
  --param param_name=param_value
```

**Running Tests:**
```bash
# Run specific package tests
cd packages/wirl-pregel-runner
make test

# Or use uv directly
uv run pytest tests/
```

### How to Run New Workflows

**From Command Line:**
```bash
python -m wirl_pregel_runner.pregel_runner \
  path/to/workflow.wirl \
  --functions module.path.to.implementation \
  --param key=value
```

**From Frontend (when implemented):**
- Workflows will be discoverable through the backend API
- Frontend provides UI for parameter input and execution monitoring
- Results displayed in web interface

**Using GitHub Actions:**
- Create workflow-specific GitHub Actions in `.github/workflows/`
- Actions can trigger workflow execution on push/PR
- Example pattern:
```yaml
name: Run My Workflow
on: [push]
jobs:
  run-workflow:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: make workflows-setup
      - name: Run workflow
        run: |
          . .venv/bin/activate
          python -m wirl_pregel_runner.pregel_runner \
            workflow_definitions/my_workflow/my_workflow.wirl \
            --functions workflow_definitions.my_workflow.my_workflow
```

## Key Development Patterns

**Workflow Function Signature:**
- All workflow functions take `(input_params..., config: dict) -> dict`
- Return dictionary with keys matching WIRL output declarations
- Use `config` for constants defined in WIRL

**Error Handling:**
- Use Python logging: `logger = logging.getLogger(__name__)`
- Raise exceptions for workflow failures
- Return structured data for successful operations

**Dependencies:**
- Each workflow manages its own `requirements.txt`
- Install all workflow deps into shared `.venv` via `make workflows-setup`
- Pin versions to avoid conflicts

**VSCode Support:**
- Install syntax extension from `extensions/vscode/`
- Provides syntax highlighting for `.wirl` files
- Package with `vsce package` and install locally