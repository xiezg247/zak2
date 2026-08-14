#!/usr/bin/env bash
# 启动 Ops ARQ worker（与 API 分离；消费 zak2:arq 队列）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
exec uv run arq app.worker.settings.WorkerSettings
