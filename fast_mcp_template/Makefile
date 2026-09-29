.PHONY: dev run test lint fmt migrate revision docker-up docker-down

# Local dev server. `fastapi dev` (from fastapi-cli, github.com/fastapi/fastapi-cli)
# already gives you reload + localhost binding + FASTAPI_ENV=development --
# no reason to hand-write a uvicorn.run() call for this.
dev:
	poetry run fastapi dev app/main.py

# Production-mode server (reload off, binds 0.0.0.0) -- what the Docker image's CMD runs.
run:
	poetry run fastapi run app/main.py

test:
	poetry run pytest

lint:
	poetry run ruff check .

fmt:
	poetry run ruff check --fix .
	poetry run ruff format .

# Apply migrations up to head.
migrate:
	poetry run alembic upgrade head

# Autogenerate a migration from model changes: make revision m="add foo column"
revision:
	poetry run alembic revision --autogenerate -m "$(m)"

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v
