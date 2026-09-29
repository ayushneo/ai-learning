.PHONY: venv sync compile dev run test lint fmt migrate revision docker-up docker-down

VENV := .venv/bin

# One-time (or after a pyenv version bump): create the venv against the
# pyenv-pinned interpreter named in .python-version.
venv:
	pyenv install --skip-existing $$(cat .python-version)
	pyenv exec python -m venv .venv
	$(VENV)/pip install --upgrade pip pip-tools

# Install from the locked requirements files -- no resolution at install time.
sync:
	$(VENV)/pip-sync requirements.txt requirements-dev.txt

# Re-resolve locks from pyproject.toml after a dependency change.
compile:
	$(VENV)/pip-compile pyproject.toml -o requirements.txt
	$(VENV)/pip-compile pyproject.toml --extra dev -o requirements-dev.txt

# Local dev server. `fastapi dev` (from fastapi-cli, github.com/fastapi/fastapi-cli)
# already gives you reload + localhost binding + FASTAPI_ENV=development --
# no reason to hand-write a uvicorn.run() call for this.
dev:
	$(VENV)/fastapi dev app/main.py

# Production-mode server (reload off, binds 0.0.0.0) -- what the Docker image's CMD runs.
run:
	$(VENV)/fastapi run app/main.py

test:
	$(VENV)/pytest

lint:
	$(VENV)/ruff check .

fmt:
	$(VENV)/ruff check --fix .
	$(VENV)/ruff format .

# Apply migrations up to head.
migrate:
	$(VENV)/alembic upgrade head

# Autogenerate a migration from model changes: make revision m="add foo column"
revision:
	$(VENV)/alembic revision --autogenerate -m "$(m)"

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v
