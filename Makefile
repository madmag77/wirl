.PHONY: workflows-setup workflows-setup-dev init-venv check-uv check-overmind install-core install-core-dev install-workflow-deps install-backend-deps install-worker-deps test-workflow test-all-workflows run-workflow run_wirl_apps install-frontend-deps get_telegram_chat_id

ROOT := $(CURDIR)
VENV := $(ROOT)/.venv
PY := $(VENV)/bin/python

check-uv:
	@command -v uv >/dev/null 2>&1 || { echo "uv is required: see https://docs.astral.sh/uv/"; exit 1; }

init-venv: check-uv
	uv venv $(VENV)

install-core: init-venv
	UV_PYTHON=$(PY) $(MAKE) -C $(ROOT)/packages/wirl-lang install
	UV_PYTHON=$(PY) $(MAKE) -C $(ROOT)/packages/wirl-pregel-runner install

install-core-dev: init-venv
	UV_PYTHON=$(PY) $(MAKE) -C $(ROOT)/packages/wirl-lang install-dev
	UV_PYTHON=$(PY) $(MAKE) -C $(ROOT)/packages/wirl-pregel-runner install-dev

WORKFLOW_REQS := $(shell find $(ROOT)/workflow_definitions -type f -name requirements.txt 2>/dev/null)

install-workflow-deps: init-venv
	@if [ -z "$(WORKFLOW_REQS)" ]; then echo "No workflow requirements found."; else \
	  for req in $(WORKFLOW_REQS); do \
	    echo "Installing workflow deps from $$req"; \
	    uv pip install --python $(PY) -r "$$req"; \
	  done; \
	fi

install-backend-deps: init-venv
	$(MAKE) -C $(ROOT)/apps/backend install

install-worker-deps: init-venv
	$(MAKE) -C $(ROOT)/apps/workers install

install-frontend-deps: init-venv
	$(MAKE) -C $(ROOT)/apps/frontend install

check-overmind:
	@command -v overmind >/dev/null 2>&1 || { echo "overmind is required: install with 'brew install overmind'"; exit 1; }

run_wirl_apps: check-overmind
	overmind start -f $(ROOT)/procfile

workflows-setup: install-core install-workflow-deps install-backend-deps install-worker-deps install-frontend-deps
	@echo "Workflows environment is ready in $(VENV)"

workflows-setup-dev: install-core-dev install-workflow-deps install-backend-deps install-worker-deps
	@echo "Workflows development environment is ready in $(VENV)"

#
# Testing workflows
#
# Usage examples:
#   make test-workflow WORKFLOW=paper_rename_workflow             # run one workflow's tests
#   make test-all-workflows                                       # run all workflow tests
#   make test-workflow WORKFLOW=paper_rename_workflow PYTEST_ARGS="-q -k mytest"

# Optional: name of workflow directory under workflow_definitions/
WORKFLOW ?=
# Optional: extra args to pass to pytest (default: -q)
PYTEST_ARGS ?= -q

ifeq ($(strip $(WORKFLOW)),)
TEST_TARGET := $(ROOT)/workflow_definitions
else
TEST_TARGET := $(ROOT)/workflow_definitions/$(WORKFLOW)/tests
endif

test-workflow: check-uv
	uv run --with $(ROOT)/packages/wirl-pregel-runner -- pytest $(TEST_TARGET) $(PYTEST_ARGS)

test-all-workflows: check-uv
	uv run --with $(ROOT)/packages/wirl-pregel-runner -- pytest $(ROOT)/workflow_definitions $(PYTEST_ARGS)

#
# Running a workflow from the DSL file
#
# Usage examples:
#   make run-workflow WORKFLOW=paper_rename_workflow FUNCS=workflow_definitions.paper_rename_workflow.paper_rename_workflow \
#        PARAMS="drafts_folder_path=/abs/path processed_folder_path=/abs/path"
#
# Required:
#   WORKFLOW: directory name under workflow_definitions/
#   FUNCS: Python module with workflow functions (import path)
# Optional:
#   PARAMS: space-separated key=value pairs passed as --param to the runner

WORKFLOW ?=
FUNCS ?=
PARAMS ?=

define PARAM_FLAGS
$(foreach p,$(PARAMS),--param $(p))
endef

run-workflow: check-uv
	@if [ -z "$(WORKFLOW)" ] || [ -z "$(FUNCS)" ]; then \
	  echo "Usage: make run-workflow WORKFLOW=<dir> FUNCS=<module.path> [PARAMS=\"k=v k2=v2\"]"; \
	  exit 1; \
	fi
	uv run --with $(ROOT)/packages/wirl-pregel-runner -- \
	  python -m wirl_pregel_runner.pregel_runner \
	  $(ROOT)/workflow_definitions/$(WORKFLOW)/$(WORKFLOW).wirl \
	  --functions $(FUNCS) \
	  $(PARAM_FLAGS)

# Get Telegram chat ID
# Requires: .env file with TELEGRAM_BOT_TOKEN=your_token
# Usage: make get_telegram_chat_id
get_telegram_chat_id:
	@if [ -f .env ]; then \
		set -a && . ./.env && set +a; \
	fi; \
	if [ -z "$$TELEGRAM_BOT_TOKEN" ]; then \
		echo "Error: TELEGRAM_BOT_TOKEN not set. Create .env file with TELEGRAM_BOT_TOKEN=your_token"; \
		exit 1; \
	fi; \
	curl "https://api.telegram.org/bot$$TELEGRAM_BOT_TOKEN/getUpdates" | jq '.result[0].message.chat.id'

#
# Repository-wide tests
#
.PHONY: test test-python-packages test-workflows

# Run all tests (Python packages, workflows, and frontend)
test: test-python-packages test-all-workflows
	@echo "All tests completed"

# Python package tests (ensures dev deps like pytest are installed)
test-python-packages:
	$(MAKE) -C $(ROOT)/packages/wirl-pregel-runner test PY=$(PY)

# Alias for clarity (reuses existing target)
test-workflows: test-all-workflows
