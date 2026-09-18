.PHONY: bootstrap check test format doctor

bootstrap:
	uv sync --frozen

check:
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .
	uv run --frozen pytest
	uv run --frozen python scripts/check_docs.py

test:
	uv run --frozen pytest

format:
	uv run --frozen ruff format .

doctor:
	uv run --frozen nisayon doctor
