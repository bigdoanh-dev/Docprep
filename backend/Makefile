.PHONY: install test lint ollama web

install:
	uv sync

test:
	uv run pytest -q

lint:
	uv run ruff check yhdp tests

# Start the local model server for this session (not installed as a service).
ollama:
	ollama serve

# Build the learner and reviewer apps from the repository root.
web:
	cd ../web && npm ci && npm run build
	cd ../web-review && npm ci && npm run build
