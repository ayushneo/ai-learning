#!/bin/sh
set -e

migrate -path /app/migrations -database "$DATABASE_URL" up

exec "$@"
