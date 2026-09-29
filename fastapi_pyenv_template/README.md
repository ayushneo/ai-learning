# fastapi_pyenv_template

Same reusable backend skeleton as [`../fastapi_template`](../fastapi_template), with the
packaging layer swapped for **pyenv (interpreter version) + pip-tools (dependency resolution
and locking)** — two small, boring, separately-replaceable tools instead of Poetry's one. The
app code — routes, services, repositories, models, migrations, tests — is untouched; only
packaging changed. Copy this directory to start a new project, delete the `items` resource
once you've read how it's wired, and build your real resources the same shape.

See [`../fastapi_uv_template`](../fastapi_uv_template) for the sibling variant that collapses
both concerns into uv alone — the trade-off table below compares all three.

## File structure

```
fastapi_pyenv_template/
├── app/                        -- identical to fastapi_template/app, see that README
├── migrations/                  -- Alembic, reads the DB URL from Settings (one source of truth)
├── tests/                        -- AsyncClient + in-memory SQLite, no docker-compose needed to run pytest
├── .python-version                -- pyenv's pin: `pyenv install`/`pyenv local` read this
├── Dockerfile                      -- multi-stage: plain venv + pip in `builder`, slim `runtime`
├── docker-compose.yml                -- app + Postgres with a healthcheck-gated startup order
├── Makefile                           -- venv/sync/compile/dev/run/test/lint/migrate
├── pyproject.toml                      -- PEP 621 metadata; pip-compile reads it directly
├── requirements.txt                     -- pip-compile output, prod deps, committed
└── requirements-dev.txt                  -- pip-compile output, prod+dev deps, committed
```

## Why pyenv + pip-tools instead of Poetry or uv

pyenv only does one job — install and pin a specific CPython build (`pyenv install`, `pyenv
local`, writes `.python-version`) — and does nothing about packages at all. pip-tools only does
one job too: resolve `pyproject.toml`'s loose version ranges into a fully pinned, hashed
`requirements.txt` (`pip-compile`), then install exactly that (`pip-sync`). Neither tool knows
the other exists; `python -m venv` is the stdlib glue between them. That's the whole trade-off
versus Poetry/uv: more moving parts, but each part is small, old, and replaceable on its own.

| Concern | Poetry (`fastapi_template`) | pyenv + pip-tools (this template) | uv alone (`fastapi_uv_template`) |
|---|---|---|---|
| Interpreter version | Uses whatever `python` it finds, unless you separately install pyenv and `poetry env use $(pyenv which python)`. | pyenv's actual job — `pyenv install`/`pyenv local`, one file, one command, nothing else does this. | `uv sync` reads `.python-version` and downloads a matching CPython itself — convenient, but it's uv making that call, not a dedicated version manager. |
| Dependency resolution + lock | Own Python resolver, own lockfile format (`poetry.lock`). | `pip-compile` — a thin, mature layer over pip's own resolver; output is a plain `requirements.txt` any tool can read, with hashes for supply-chain pinning. Slower to resolve than uv (seconds, not sub-second) but it's the most-audited resolver of the three by dint of age. | Rust resolver, standard `uv.lock`. Fastest of the three; `uv sync --group dev` resolved 57 packages in well under a second cold in the sibling template. |
| Install step | `poetry install` | `pip-sync requirements.txt requirements-dev.txt` — installs exactly the lock, removes anything not in it (unlike plain `pip install -r`). | `uv sync` |
| Project metadata | Poetry-specific `[tool.poetry.dependencies]` — needs a Poetry plugin for other tools to read it. | Plain PEP 621 `[project.dependencies]` / `[project.optional-dependencies]` — pip-compile reads `pyproject.toml` directly, no separate `requirements.in` needed. | Plain PEP 621 `[project.dependencies]`. |
| Task running | `poetry run <cmd>` | Activate `.venv` then run directly, or `.venv/bin/<cmd>` (the Makefile does the latter) | `uv run <cmd>` |
| Docker build | Installer script (`curl \| python3 -`) pulls Poetry into the builder stage at build time. | No extra tool needed — `pip install -r requirements.txt` is already in every base image; pyenv itself never enters the container (the base image tag is Docker's version pin). | Static binary copied in via `COPY --from=ghcr.io/astral-sh/uv`, no network install step. |
| Maturity / ecosystem | Older, widest adoption, most prior art for edge cases (plugin conflicts, private-index auth). | pip + venv are stdlib-adjacent and as old as Python packaging gets; pip-tools is a thin, boring, extremely well-understood layer — the safest choice if "least novel tooling" is the priority. | Newer (Astral, 2024). Core workflow used here is stable, but less prior art than Poetry or pip-tools for advanced cases. |

**Chosen for this variant:** pyenv + pip-tools, for the case where you specifically want
interpreter management and dependency locking to stay two independent, swappable tools — e.g.
one pyenv-managed interpreter shared system-wide across several projects, each with its own
pip-tools lock, or a team standardized on pip-tools already and only wants pyenv added for
reproducible interpreter pins. The real cost is two commands to remember instead of one
(`make compile` after a dependency change, then `make sync` — uv or Poetry fold this into a
single `sync`/`install`), and a slower resolver than uv's. If that two-step friction outweighs
the "small boring separable tools" benefit, use `fastapi_uv_template` instead.

Everything else — layered request flow, models-vs-schemas split, domain exceptions, the
`fastapi-tips` comments in code, the trade-offs on pagination/logging/session-lifetime/tracing
— is identical to `fastapi_template`; see that README, it wasn't duplicated here to avoid the
two copies drifting out of sync.

## Quick start

```bash
cp .env.example .env
make venv          # pyenv install (if needed) + pyenv local + venv + pip-tools bootstrap
make sync          # pip-sync from the committed lock files
make migrate       # or: .venv/bin/alembic revision --autogenerate -m "init" && make migrate
make dev           # fastapi dev app/main.py -- reload on, http://127.0.0.1:8000/docs
make test
```

Or with Docker (app + Postgres, migrations run automatically before the server starts —
see `scripts/docker-entrypoint.sh`):

```bash
make docker-up
```

## Extending this template

- **New resource**: add `models/foo.py`, `schemas/foo.py`, `repositories/foo.py` (subclass
  `BaseRepository[Foo]`), `services/foo.py`, `api/v1/foo.py`, then one line in `api/v1/router.py`.
  Copy `items.py`'s shape end to end — that's what it's there to demonstrate.
- **New migration**: `make revision m="add foo table"`, review the autogenerated file, `make migrate`.
- **New dependency**: add it to `pyproject.toml`'s `dependencies` (or the `dev` extra), then
  `make compile && make sync` — mirrors `poetry add` / `uv add` as a two-step instead of one.
- **Auth**: not included — it's the one piece genuinely specific to each project (session vs. JWT
  vs. OAuth2 provider). Add it as a `Depends()` in `api/deps.py`, following the same pattern as `get_db`.

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-17 | Forked from `fastapi_template` as a separate variant from `fastapi_uv_template`; swapped Poetry for pyenv (interpreter) + pip-tools (locking) (pyproject.toml, Dockerfile, Makefile), added `.python-version`, `requirements.txt`, `requirements-dev.txt` generated via `pip-compile` against a real pyenv-installed 3.11.10, verified `pytest`/`ruff` pass against the compiled lock | Ayush Sood |
