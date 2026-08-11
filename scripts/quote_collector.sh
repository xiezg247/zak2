#!/usr/bin/env bash
# 启动 zak2 行情采集进程（与 API 分离；本实例内勿多开 collector）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
exec uv run python -m app.quote_collector
