.PHONY: install install-dev lint lint_diff format format_diff

# Files selection
PYTHON_FILES=.

# Diff-aware selections (against main)
lint format: PYTHON_FILES=.
lint_diff format_diff: PYTHON_FILES=$(shell git diff --name-only --relative --diff-filter=d main . | grep -E '\.py$$|\.ipynb$$')

install:
	uv pip install -e .

install-dev:
	uv pip install -e '.[dev]'

lint lint_diff:
	uv run ruff check $(PYTHON_FILES)

format format_diff:
	uv run ruff format $(PYTHON_FILES)
	uv run ruff check --select I --fix $(PYTHON_FILES)

