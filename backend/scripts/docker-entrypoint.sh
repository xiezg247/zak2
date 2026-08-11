#!/usr/bin/env bash
set -euo pipefail
echo "alembic upgrade head..."
alembic upgrade head
exec "$@"
