.PHONY: dev run test lint fmt migrate revision docker-up docker-down

# Local dev server. `fastapi dev` (from fastapi-cli, github.com/fastapi/fastapi-cli)
# already gives you reload + localhost binding + FASTAPI_ENV=development --
# no reason to hand-write a uvicorn.run() call for this.
dev:
	uv run fastapi dev app/main.py

# Production-mode server (reload off, binds 0.0.0.0) -- what the Docker image's CMD runs.
run:
	uv run fastapi run app/main.py

test:
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

# Apply migrations up to head.
migrate:
	uv run alembic upgrade head

# Autogenerate a migration from model changes: make revision m="add foo column"
revision:
	uv run alembic revision --autogenerate -m "$(m)"

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v
