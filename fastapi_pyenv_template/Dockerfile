# Multi-stage build: `builder` has the C compiler wheels that need one
# (asyncpg, etc); `runtime` copies only the built virtualenv out of it. No
# packaging tool to install here at all -- pip is already in the base image,
# and the base image tag (`python:3.11-slim`) is Docker's equivalent of
# pyenv's version pin. pyenv itself is a local-dev-only concern; it has no
# role inside the container.
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install --no-install-recommends -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN python -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY requirements.txt ./
# requirements.txt is pip-compile's fully pinned + hashed output -- no
# resolution happens at build time, same reproducibility guarantee Poetry's
# lock / uv's lock give you.
RUN pip install --no-cache-dir -r requirements.txt

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
