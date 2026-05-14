.PHONY: help install test lint format format-check type-check check build clean

PY ?= .venv/bin/python

help:  ## Show available targets
	@awk -F':.*##' '/^[a-zA-Z_-]+:.*##/{printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Install package + dev dependencies in editable mode
	$(PY) -m pip install -e ".[dev]"

test:  ## Run pytest
	$(PY) -m pytest -q

lint:  ## Run ruff check
	$(PY) -m ruff check src tests

format:  ## Apply ruff formatting fixes
	$(PY) -m ruff check --fix src tests

format-check:  ## Verify ruff is clean (CI-style)
	$(PY) -m ruff check src tests

type-check:  ## Run mypy
	$(PY) -m mypy src/ai_configurator

check: lint type-check test  ## Run all quality gates

build:  ## Build sdist + wheel
	$(PY) -m build

clean:  ## Remove build artefacts
	rm -rf build dist *.egg-info .mypy_cache .pytest_cache .ruff_cache
