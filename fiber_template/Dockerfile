# Multi-stage build: `builder` compiles a static binary; `runtime` ships
# only that binary plus CA certs (needed for TLS to a managed Postgres).
# CGO_ENABLED=0 works because the shipped binary only imports the pure-Go
# postgres driver (jackc/pgx) -- the sqlite driver (mattn/go-sqlite3, cgo)
# is test-only and never gets compiled into cmd/api. No compiler toolchain
# to strip out of the runtime image, unlike the Python templates' Dockerfiles.
FROM golang:1.25-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app/server ./cmd/api

# ---------------------------------------------------------------------------
FROM alpine:3.22 AS runtime

RUN apk add --no-cache ca-certificates \
    && adduser -D -u 10001 appuser

WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/server ./server
# golang-migrate's own image ships one static binary -- copied in the same
# no-installer-script way the pyenv_template's Dockerfile copies uv, instead
# of `go install`-ing it in the builder stage.
COPY --from=migrate/migrate:v4.20.1 /usr/local/bin/migrate /usr/local/bin/migrate
COPY --chown=appuser:appuser migrations ./migrations
COPY --chown=appuser:appuser scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh

USER appuser
EXPOSE 8000

ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
CMD ["./server"]
