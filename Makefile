.PHONY: lint format

lint:
	uv run ruff check
	uv run ty check

format:
	uv run ruff check --fix
	uv run ruff format
