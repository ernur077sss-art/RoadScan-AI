#!/bin/sh
set -eu

# Production migrations are a separate release step, before new replicas start.
# Keep the existing one-command startup for the local Docker Compose environment.
if [ "${ROADSCAN_ENV:-development}" != "production" ]; then
  python -m alembic upgrade head
fi

exec python -m uvicorn api.main:app \
  --host 0.0.0.0 --port "${PORT:-8000}" \
  --no-access-log --no-proxy-headers
