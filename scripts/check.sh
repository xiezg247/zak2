#!/usr/bin/env bash
# 本地验收：pytest + 前端 build
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> backend pytest"
(cd backend && uv run pytest -q)

echo "==> frontend build"
(cd frontend && npm run build)

echo "OK：测试与构建通过"
