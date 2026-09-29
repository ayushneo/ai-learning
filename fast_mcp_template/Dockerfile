# Multi-stage build: `builder` has poetry + a C compiler for wheels that need
# one (asyncpg, etc); `runtime` copies only the built virtualenv out of it.
# The alternative -- one stage, poetry installed in the final image -- is
# fewer lines but ships a compiler toolchain and poetry itself to production
# for no runtime benefit. Multi-stage is the standard trade-off here because
# image size/attack-surface actually matters for something you deploy.
FROM python:3.11-slim AS builder

ENV POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install --no-install-recommends -y curl gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app
COPY pyproject.toml poetry.lock* ./
# --without dev: skip pytest/ruff/aiosqlite -- they have no reason to be in
# the image that runs in production.
RUN poetry install --without dev --no-root

COPY . .

# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install --no-install-recommends -y libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/.venv .venv
COPY --chown=appuser:appuser . .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8000

ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
# `fastapi run` (not `fastapi dev`): reload off, binds 0.0.0.0 -- see
# app/main.py's docstring for the dev/prod split fastapi-cli gives you free.
CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
