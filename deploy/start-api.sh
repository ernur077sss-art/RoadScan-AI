#!/bin/sh
set -eu

# Default production uses a separate release step. Render Free has no release
# jobs, so its blueprint explicitly opts into locked migrations before startup.
if [ "${ROADSCAN_MIGRATE_ON_START:-0}" = "1" ] || [ "${ROADSCAN_ENV:-development}" != "production" ]; then
  python -m api.migrate
fi

exec python -m uvicorn api.main:app \
  --host 0.0.0.0 --port "${PORT:-8000}" \
  --no-access-log --no-proxy-headers
