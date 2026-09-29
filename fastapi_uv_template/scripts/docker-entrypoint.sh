#!/bin/sh
# Run pending migrations before the app starts serving traffic, then hand
# off to the container's real CMD. `exec` (not a plain call) replaces this
# shell with the CMD process so it becomes PID 1 and receives SIGTERM
# directly -- without it, `docker stop` waits out the full timeout and kills
# the app rather than letting it shut down gracefully.
set -e

alembic upgrade head

exec "$@"
