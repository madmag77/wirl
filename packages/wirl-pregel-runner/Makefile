.PHONY: install install-dev lint lint_diff format format_diff run test test_cov

# Virtual environment setup
ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || echo $(CURDIR)/../..)
VENV := $(ROOT)/.venv
PY := $(VENV)/bin/python

# Files selection
PYTHON_FILES=.

# Diff-aware selections (against main)
lint format: PYTHON_FILES=.
lint_diff format_diff: PYTHON_FILES=$(shell git diff --name-only --relative --diff-filter=d main . | grep -E '\.py$$|\.ipynb$$')

install:
	uv pip install --python $(PY) -e .

install-dev:
	uv pip install --python $(PY) -e . --group dev

lint lint_diff:
	$(PY) -m ruff check $(PYTHON_FILES)

format format_diff:
	$(PY) -m ruff format $(PYTHON_FILES)
	$(PY) -m ruff check --select I --fix $(PYTHON_FILES)

# Run the pregel runner with a workflow and parameters
# Usage examples:
#  make run WORKFLOW=../../workflow_definitions/paper_rename_workflow/paper_rename_workflow.wirl PARAMS="query='foo bar' limit=3" FUNCTIONS=workflow_definitions.paper_rename_workflow.paper_rename_workflow
#  make run WORKFLOW=../../examples/sample.wirl PARAMS="x=1 y=2"
WORKFLOW?=../../examples/sample.wirl
PARAMS?=
FUNCTIONS?=steps.deepresearch_functions
THREAD_ID?=cli
RESUME?=

run:
	$(PY) -m pregel_runner.pregel_runner $(WORKFLOW) $(foreach p,$(PARAMS),--param $(p)) --functions $(FUNCTIONS) --thread-id $(THREAD_ID) $(if $(RESUME),--resume '$(RESUME)')

test:
	$(PY) -m pytest -q tests

test_cov:
	$(PY) -m pytest -q tests --cov=pregel_runner --cov-report=term-missing
