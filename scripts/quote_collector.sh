#!/usr/bin/env bash
# 启动 zak2 行情采集进程（与 API 分离；勿与 zak CLI collect_quotes 双写同一 Redis）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
exec uv run python -m app.quote_collector
