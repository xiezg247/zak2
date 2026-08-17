#!/usr/bin/env bash
# 本地验收：后端 lint/format/mypy/pytest + 前端 lint/format/build
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> backend ruff check"
(cd backend && uv run ruff check .)

echo "==> backend ruff format --check"
(cd backend && uv run ruff format --check .)

echo "==> backend mypy"
(cd backend && uv run mypy app)

echo "==> backend pytest"
(cd backend && uv run pytest -q)

echo "==> frontend eslint"
(cd frontend && npm run lint:check)

echo "==> frontend prettier --check"
(cd frontend && npm run format:check)

echo "==> frontend build"
(cd frontend && npm run build)

echo "OK：lint / format / type / test / build 全部通过"
