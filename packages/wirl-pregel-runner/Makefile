.PHONY: install install-dev lint lint_diff format format_diff run test test_cov

# Files selection
PYTHON_FILES=.

# Diff-aware selections (against main)
lint format: PYTHON_FILES=.
lint_diff format_diff: PYTHON_FILES=$(shell git diff --name-only --relative --diff-filter=d main . | grep -E '\.py$$|\.ipynb$$')

install:
	uv pip install -e .

install-dev:
	uv pip install -e . --group dev

lint lint_diff:
	uv run ruff check $(PYTHON_FILES)

format format_diff:
	uv run ruff format $(PYTHON_FILES)
	uv run ruff check --select I --fix $(PYTHON_FILES)

# Run the pregel runner with a workflow and parameters
# Usage examples:
#  make run WORKFLOW=../../workflow_definitions/paper_rename_workflow/paper_rename_workflow.awsl PARAMS="query='foo bar' limit=3" FUNCTIONS=workflow_definitions.paper_rename_workflow.paper_rename_workflow
#  make run WORKFLOW=../../examples/sample.awsl PARAMS="x=1 y=2"
WORKFLOW?=../../examples/sample.awsl
PARAMS?=
FUNCTIONS?=steps.deepresearch_functions
THREAD_ID?=cli
RESUME?=
DEBUG?=

run:
	uv run python -m pregel_runner.pregel_runner $(WORKFLOW) $(foreach p,$(PARAMS),--param $(p)) --functions $(FUNCTIONS) --thread-id $(THREAD_ID) $(if $(RESUME),--resume '$(RESUME)')

test:
	python -m pytest -q tests

test_cov:
	python -m pytest -q tests --cov=pregel_runner --cov-report=term-missing


