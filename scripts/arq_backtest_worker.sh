#!/usr/bin/env bash
# 启动回测 ARQ worker（消费 zak2:arq:backtest；需 uv sync --extra backtest）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
export BACKTEST_SUBPROCESS="${BACKTEST_SUBPROCESS:-1}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
exec uv run --extra backtest arq app.worker.settings_backtest.WorkerSettings
