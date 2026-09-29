.PHONY: dev run build test lint fmt migrate revision docker-up docker-down

DATABASE_URL ?= postgres://postgres:postgres@localhost:5432/app?sslmode=disable

# No task-runner wrapper needed -- `go run`/`go test`/`go build` already run
# against the module directly, unlike `poetry run`/`uv run`: Go's toolchain
# has no separate venv to activate.
dev:
	go run ./cmd/api

run: build
	./server

build:
	CGO_ENABLED=0 go build -o server ./cmd/api

test:
	go test ./...

lint:
	go vet ./...
	gofmt -l .

fmt:
	gofmt -w .

# Apply migrations up to the latest. Requires golang-migrate's CLI:
# https://github.com/golang-migrate/migrate/tree/master/cmd/migrate
migrate:
	migrate -path migrations -database "$(DATABASE_URL)" up

# New migration pair: make revision name=add_foo_column
revision:
	migrate create -ext sql -dir migrations -seq $(name)

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v
