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

APP_MODULE?=workers.worker_pool:main

install:
	uv pip install --python $(PY) -e .

install-dev:
	uv pip install --python $(PY) -e . --group dev

lint lint_diff:
	$(PY) -m ruff check $(PYTHON_FILES)

format format_diff:
	$(PY) -m ruff format $(PYTHON_FILES)
	$(PY) -m ruff check --select I --fix $(PYTHON_FILES)

run:
	$(PY) -m workers.worker_pool

test:
	$(PY) -m pytest -q tests

test_cov:
	$(PY) -m pytest -q tests --cov=workers --cov-report=term-missing




