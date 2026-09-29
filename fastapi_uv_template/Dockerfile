# Multi-stage build: `builder` has the C compiler wheels that need one
# (asyncpg, etc) plus uv itself; `runtime` copies only the built virtualenv
# out of it. uv ships as a single static binary (COPY --from=ghcr image, no
# installer script, no Rust/pip bootstrap) so `builder` is lighter than the
# Poetry equivalent, but the two-stage split is still worth it: the compiler
# toolchain has no reason to ship to production.
FROM python:3.11-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /usr/local/bin/uv

RUN apt-get update && apt-get install --no-install-recommends -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
# --no-dev: skip pytest/ruff/aiosqlite -- they have no reason to be in the
# image that runs in production. --frozen: fail instead of silently
# re-resolving if uv.lock drifted from pyproject.toml.
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

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
