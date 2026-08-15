.PHONY: install test lint typecheck verify search

install:
	uv sync --extra dev

test:
	uv run --extra dev pytest

lint:
	uv run --extra dev ruff check .

typecheck:
	uv run --extra dev mypy src

verify: lint typecheck test

search:
	uv run dealfinder search

