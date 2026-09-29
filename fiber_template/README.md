# fiber_template

Reusable starting point for Go backend services, not a specific product — the Fiber
counterpart to [`../fastapi_template`](../fastapi_template): same layered shape (route →
service → repository → model), same "delete the `items` resource once you've read it" intent.
Copy this directory to start a new project.

One packaging note up front: the fastapi_* templates come in three flavors (Poetry, uv,
pyenv+pip-tools) because Python has three real competing dependency-management ecosystems.
Go doesn't — `go mod`/`go.sum` is the one blessed toolchain, built into `go build` itself. So
there's exactly one Go template here, not three; templating a packaging-tool choice that
doesn't exist would be solving a problem Go doesn't have.

Written by reading three references, not by cloning any of them:

| Reference | What was actually taken from it |
|---|---|
| [alpody/golang-fiber-realworld-example-app](https://github.com/alpody/golang-fiber-realworld-example-app) | Confirmed the layered shape (`handler` → `store`/service → `model`) and the stack choice (Fiber + GORM + go-playground/validator + testify) for a "real" Fiber CRUD backend, not a toy. Not taken: JWT auth wired by default, SQLite-as-primary-DB (it uses SQLite with Postgres commented out; this template inverts that — Postgres primary, SQLite for tests only), Swagger annotations, and its `AutoMigrate`-on-boot pattern in `main.go` — this template uses versioned SQL migration files instead, for the same reason `fastapi_template` uses Alembic over ad hoc table creation. |
| [gofiber/awesome-fiber](https://github.com/gofiber/awesome-fiber) | Confirmed `requestid`, `recover`, `logger`, and `cors` all ship in Fiber core — nothing to hand-write here, unlike `fastapi_template`'s `middleware/request_id.py` (Starlette has no built-in request-ID middleware, so that one's a real hand-roll). Also where the "boilerplates" and "recipes" categories pointed at the next reference. |
| [gofiber/recipes](https://github.com/gofiber/recipes) | `graceful-shutdown` recipe's exact shutdown pattern (`go func(){ app.Listen() }()` + signal channel + `ShutdownWithTimeout`), used verbatim in `cmd/api/main.go`. `clean-architecture` and `gorm-postgres` recipes confirmed the directory split (a `models`/`database`/routes layering) independently of the realworld app. Not taken: recipe folders are single-concept demos (one recipe = one middleware or one integration, no layered CRUD app to copy directly) — the layered structure came from the realworld app and `fastapi_template`, not from any one recipe folder. |

## File structure

```
fiber_template/
├── cmd/api/main.go                -- app factory: config, DB, middleware, routes, graceful shutdown
├── internal/
│   ├── config/                     -- os.Getenv + defaults, no viper (pydantic-settings' Go
│   │                                   analog would be a struct-tag reflection lib for 3 fields)
│   ├── db/                          -- GORM Postgres connection + pool tuning
│   ├── apperror/                     -- typed errors + one handler (fiber.Config.ErrorHandler)
│   ├── models/                        -- GORM structs (DB shape)
│   ├── repository/                     -- DB queries only; one generic Base[T] (Go generics) + Item
│   ├── service/                         -- business logic; thin here, same as fastapi_template
│   └── handler/                          -- routes + request/response DTOs + validation
├── migrations/                             -- golang-migrate SQL files, Alembic's direct analog
├── Dockerfile                                -- multi-stage: compile in `builder`, static binary in `runtime`
├── docker-compose.yml                         -- app + Postgres with a healthcheck-gated startup order
├── Makefile                                    -- dev/build/test/lint/migrate
└── go.mod / go.sum                              -- the only dependency-management story Go has
```

## Request flow

`handler (internal/handler)` → `service (internal/service)` → `repository (internal/repository)`
→ `model (internal/models)`. Same rule as `fastapi_template`: a handler never imports a
repository directly, and a repository never returns a handler-layer DTO — that boundary is what
lets you swap the DB layer without touching handlers.

## Trade-offs made, and why

| Decision | Options | Chosen, and why |
|---|---|---|
| Web framework | net/http + a router (chi/gorilla) vs. Fiber | Fiber — Express-style ergonomics (route groups, `c.Bind()`, built-in `app.Test()` for handler tests) on top of fasthttp; the realworld reference and all three cited sources are Fiber-specific, and a stdlib net/http version would be a different, longer template with no reference grounding it. |
| DB layer | Raw `database/sql`/pgx vs. GORM | GORM — closest analog to `fastapi_template`'s SQLAlchemy (an ORM, not a query builder), and what the realworld reference actually uses. sqlc/pgx would be less code generation magic and more explicit SQL, a legitimate alternative if you'd rather read exact queries than trust an ORM's generated ones. |
| Migrations | GORM `AutoMigrate` vs. versioned SQL files | Versioned files (golang-migrate) — `AutoMigrate` is what the realworld reference does in `main.go` on every boot; fine for a demo, but it can't express a column rename or a data backfill, only additive schema changes. Same call `fastapi_template` makes choosing Alembic over ad hoc `create_all`. |
| Errors | `fiber.NewError` everywhere vs. a small domain-error type + one handler | Domain errors (`internal/apperror`) — keeps HTTP status codes out of the service/repository layers, mapped once in `cmd/api/main.go`'s `fiber.Config.ErrorHandler`. For a 1-2 route toy, `fiber.NewError` directly is the more honest lazy choice; same trade-off `fastapi_template` names for `HTTPException`. |
| Request ID / recovery / access log | Hand-rolled middleware vs. Fiber core | Fiber core (`requestid`, `recover`, `logger` — confirmed shipped in-framework via awesome-fiber's middleware list) — nothing to write. The one case where this template does *less* than `fastapi_template`, because the framework does more. |
| Config | viper/envconfig vs. `os.Getenv` | `os.Getenv` + a five-field struct — no reflection-based struct-tag library for something this small. Revisit if config grows past what a human wants to eyeball in one function. |
| Logging | zerolog/zap (both in awesome-fiber's contrib list) vs. stdlib `log/slog` | stdlib `log/slog` — same call `fastapi_template` makes choosing stdlib `logging` over structlog/loguru; one dependency fewer. |
| Pagination | Keyset vs. `OFFSET`/`LIMIT` | `OFFSET`/`LIMIT`, marked with the same `ponytail:` comment `fastapi_template`'s repository base carries, naming the same ceiling. |
| Auth | JWT (what the realworld reference wires by default) vs. nothing | Nothing, by default — same call `fastapi_template` makes: auth is the one piece genuinely specific to each project. Add `gofiber/contrib/jwt` as a route-group `.Use()` the same way the realworld reference does, following its `handler/routes.go` pattern, when a project actually needs it. |
| Runtime image | `scratch` (what the realworld reference's Dockerfile uses) vs. `alpine` | `alpine` — `scratch` is smaller and what the reference does, but ships no shell and no `ca-certificates` package manager, making TLS-to-a-managed-Postgres and any future debugging harder. `alpine` costs a few MB for a shell and `apk add ca-certificates`; worth it outside a size-constrained deploy target. |

## Quick start

```bash
cp .env.example .env
set -a && source .env && set +a   # no dotenv library -- the shell already does this
go mod download
make migrate      # requires golang-migrate's CLI: https://github.com/golang-migrate/migrate
make dev          # go run ./cmd/api -- http://127.0.0.1:8000/health
make test
```

Or with Docker (app + Postgres, migrations run automatically before the server starts —
see `scripts/docker-entrypoint.sh`):

```bash
make docker-up
```

## Extending this template

- **New resource**: add `internal/models/foo.go`, a `foo` repository embedding `Base[Foo]`
  (see `internal/repository/item.go`), a `FooService`, handler methods + DTOs, then one group
  in `internal/handler/routes.go`. Copy `item.go`'s shape end to end in each layer.
- **New migration**: `make revision name=add_foo_table`, edit the generated `.up.sql`/`.down.sql`, `make migrate`.
- **Auth**: not included — see the trade-offs table above; `gofiber/contrib/jwt` on a route
  group is the realworld reference's own pattern if you need it.

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-17 | Scaffolded from golang-fiber-realworld-example-app (layered shape, Fiber+GORM+validator+testify stack), awesome-fiber (confirmed core middleware coverage), and gofiber/recipes (graceful-shutdown pattern, clean-architecture/gorm-postgres directory split); verified real `go build`, `go vet`, `go test ./...` (5 passing) and `make build`/`test`/`lint` against a freshly `brew install`ed Go 1.27.1 toolchain | Ayush Sood |
