.PHONY: install install-dev lint lint_diff format format_diff run test test_cov

# Files selection
PYTHON_FILES=.

# Diff-aware selections (against main)
lint format: PYTHON_FILES=.
lint_diff format_diff: PYTHON_FILES=$(shell git diff --name-only --relative --diff-filter=d main . | grep -E '\.py$$|\.ipynb$$')

APP_MODULE?=backend.main:app
HOST?=0.0.0.0
PORT?=8008

install:
	uv pip install -e .

install-dev:
	uv pip install -e . --group dev

lint lint_diff:
	uv run ruff check $(PYTHON_FILES)

format format_diff:
	uv run ruff format $(PYTHON_FILES)
	uv run ruff check --select I --fix $(PYTHON_FILES)

run:
	uv run uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

test:
	python -m pytest -q tests

test_cov:
	python -m pytest -q tests --cov=backend --cov-report=term-missing


