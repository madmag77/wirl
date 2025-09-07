.PHONY: workflows-setup init-venv check-uv install-core install-workflow-deps install-backend-deps install-worker-deps

ROOT := $(CURDIR)
VENV := $(ROOT)/.venv
PY := $(VENV)/bin/python

check-uv:
	@command -v uv >/dev/null 2>&1 || { echo "uv is required: see https://docs.astral.sh/uv/"; exit 1; }

init-venv: check-uv
	uv venv $(VENV)

install-core: init-venv
	uv pip install --python $(PY) -e $(ROOT)/packages/wirl-lang
	uv pip install --python $(PY) -e $(ROOT)/packages/wirl-pregel-runner

WORKFLOW_REQS := $(shell find $(ROOT)/workflow_definitions -type f -name requirements.txt 2>/dev/null)

install-workflow-deps: init-venv
	@if [ -z "$(WORKFLOW_REQS)" ]; then echo "No workflow requirements found."; else \
	  for req in $(WORKFLOW_REQS); do \
	    echo "Installing workflow deps from $$req"; \
	    uv pip install --python $(PY) -r "$$req"; \
	  done; \
	fi

install-backend-deps:
	@echo "TODO: install backend deps (placeholder)"

install-worker-deps:
	@echo "TODO: install worker deps (placeholder)"

workflows-setup: install-core install-workflow-deps install-backend-deps install-worker-deps
	@echo "Workflows environment is ready in $(VENV)"
