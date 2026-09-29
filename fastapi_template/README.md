# fastapi_template

A reusable starting point for backend services, not a specific product. Copy
this directory to start a new project, delete the `items` resource once
you've read how it's wired, and build your real resources the same shape.

Written by reading three references end to end, not by cloning any of them:

| Reference | What was actually taken from it |
|---|---|
| [rannysweis/fast-api-docker-poetry](https://github.com/rannysweis/fast-api-docker-poetry) | The layered structure (routes → services → repositories → models), Poetry + multi-stage Docker, Alembic wiring, naming resources by role (`item_repository`, `item_service`). Not taken: `@cbv` class-based controllers and OpenTelemetry/Jaeger tracing — see trade-offs below. |
| [Kludex/fastapi-tips](https://github.com/Kludex/fastapi-tips) | Applied directly in code as `# tip N` comments (grep for `tip ` to find all of them): lifespan state over `app.state`, pure ASGI middleware, async dependencies, `AsyncClient`+`ASGITransport` in tests, `pytest.mark.anyio`, `async for` on websockets. |
| [fastapi/fastapi-cli](https://github.com/fastapi/fastapi-cli) | `fastapi dev` / `fastapi run` as the actual way this app is started (see `Makefile`, `app/main.py`, `Dockerfile`) instead of a hand-rolled `uvicorn.run()` or a custom CLI wrapper — `fastapi[standard]` already ships this. |

## File structure

```
fastapi_template/
├── app/
│   ├── main.py               -- app factory: lifespan, middleware, exception handlers, routers
│   ├── core/
│   │   ├── config.py          -- pydantic-settings, one Settings singleton via lru_cache
│   │   ├── db.py               -- async engine/session, yielded as lifespan state
│   │   ├── exceptions.py        -- domain exceptions + one handler, not HTTPException everywhere
│   │   └── logging.py           -- stdlib logging.dictConfig, no structlog/loguru dependency
│   ├── api/
│   │   ├── deps.py             -- shared Depends() -- get_db, get_item_service
│   │   └── v1/                  -- versioned routes ("controllers"); router.py aggregates them
│   ├── models/                 -- SQLAlchemy ORM (DB shape)
│   ├── schemas/                -- Pydantic request/response (API shape) -- deliberately separate from models
│   ├── repositories/            -- DB queries only, one generic CRUD base + per-model subclasses
│   ├── services/                -- business logic; thin here, grows as use cases combine repositories
│   └── middleware/               -- request_id.py: a pure-ASGI middleware example
├── migrations/                  -- Alembic, reads the DB URL from Settings (one source of truth)
├── tests/                        -- AsyncClient + in-memory SQLite, no docker-compose needed to run pytest
├── Dockerfile                     -- multi-stage: poetry+compiler in `builder`, slim `runtime`
├── docker-compose.yml               -- app + Postgres with a healthcheck-gated startup order
├── Makefile                          -- dev/run/test/lint/migrate, thin wrappers over real tools
└── pyproject.toml
```

## Request flow

`route (api/v1/*.py)` → `service (services/*.py)` → `repository (repositories/*.py)` → `model (models/*.py)`.
Each layer only talks to the one below it. A route never imports a repository directly, and a
repository never returns a Pydantic schema — that boundary is what lets you swap the DB layer
(add caching in the repository, add a second data source in the service) without touching routes.

## Trade-offs made, and why

| Decision | Options | Chosen, and why |
|---|---|---|
| Controllers | Class-based (`@cbv`, from fastapi-restful, used by the docker-poetry reference) vs. plain functions + `Depends()` | Plain functions — FastAPI's own `Depends()` already shares a constructed dependency across routes; `@cbv` earns its keep once a resource needs shared *mutable* state across methods, which none here do. |
| Models vs. schemas | One class doing double duty (ORM + Pydantic) vs. two separate classes | Two — a DB column rename and an API contract change are different events; conflating them makes either change riskier. |
| Errors | Raise `HTTPException` everywhere vs. a small domain-exception hierarchy + one handler | Domain exceptions — keeps HTTP concerns (`404`) out of the service/repository layers, at the cost of one more file. For a 1-2 route toy, `HTTPException` directly is the more honest lazy choice; this template already has more than that. |
| Pagination | Keyset (`WHERE id > :cursor`) vs. `OFFSET`/`LIMIT` | `OFFSET`/`LIMIT` — simpler, and fine until someone paginates deep into a large table (marked with a `ponytail:` comment in `repositories/base.py` naming the ceiling). |
| Logging | structlog/loguru vs. stdlib `logging` | stdlib — one dependency fewer; revisit if you need contextvar-scoped structured fields threaded automatically. |
| Session lifetime | One session per app (or per-thread) vs. one per request | Per request, auto-commit/rollback at the request boundary (`api/deps.py::get_db`) — the standard default for a CRUD API; a multi-step saga should manage its own session instead of fighting this one. |
| DB URL | Duplicated in `alembic.ini` and app settings vs. one source of truth | One — `migrations/env.py` imports `Settings` directly, so `.env` changes don't need updating twice. |
| Tracing | OpenTelemetry + Jaeger (in the docker-poetry reference) vs. nothing | Nothing, by default — real observability infra is a per-deployment decision, not a template default; the request-ID middleware plus structured logs is the floor every deployment gets for free. |

## fastapi-tips applied

Every tip below is a comment in the actual code (`grep -rn "tip " app tests` to jump to each one) —
this list is just the index, not a duplicate explanation:

1. `uvloop`/`httptools` — `pyproject.toml`, `fastapi[standard]` extra; Uvicorn picks them up automatically.
2. Prefer `async def` route/dependency functions — sync ones run in a limited thread pool (`api/deps.py`).
3. `async for websocket.iter_text()` over `while True: receive_text()` — `api/v1/ws.py`.
4. `async for` also catches `WebSocketDisconnect` for you — `api/v1/ws.py`.
5. `httpx.AsyncClient` + `ASGITransport` over `TestClient` — `tests/conftest.py`.
6. Lifespan state over `app.state` — `app/core/db.py`, `app/main.py`.
7. `PYTHONASYNCIODEBUG=1` to find blocking endpoints — not wired as a Makefile target (one-off debugging, not a routine command), documented here instead.
8. Pure ASGI middleware over `BaseHTTPMiddleware` — `app/middleware/request_id.py`.
9. Sync dependencies run on a thread — `api/deps.py`'s `get_db` is `async` specifically because of this.
10. `pytest.mark.anyio` over `pytest-asyncio` — `tests/conftest.py`.

## Quick start

```bash
cp .env.example .env
poetry install
make migrate      # or: poetry run alembic revision --autogenerate -m "init" && make migrate
make dev          # fastapi dev app/main.py -- reload on, http://127.0.0.1:8000/docs
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
- **Auth**: not included — it's the one piece genuinely specific to each project (session vs. JWT
  vs. OAuth2 provider). Add it as a `Depends()` in `api/deps.py`, following the same pattern as `get_db`.

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-13 | Scaffolded from fast-api-docker-poetry (structure/Docker/Poetry), fastapi-tips (in-code tip comments), and fastapi-cli (dev/run workflow) | Ayush Sood |
