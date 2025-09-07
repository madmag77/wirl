.PHONY: workflows-setup workflows-setup-dev init-venv check-uv install-core install-core-dev install-workflow-deps install-backend-deps install-worker-deps

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

install-backend-deps:
	@echo "TODO: install backend deps (placeholder)"

install-worker-deps:
	@echo "TODO: install worker deps (placeholder)"

workflows-setup: install-core install-workflow-deps install-backend-deps install-worker-deps
	@echo "Workflows environment is ready in $(VENV)"

workflows-setup-dev: install-core-dev install-workflow-deps install-backend-deps install-worker-deps
	@echo "Workflows development environment is ready in $(VENV)"
