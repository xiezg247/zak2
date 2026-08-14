#!/usr/bin/env bash
# 本地一键启动：后端 :8000 + 前端 :5173
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "已从 .env.example 生成 .env，请按需填写 DATABASE_URL / JWT_SECRET / 密钥"
  else
    echo "缺少 .env，请先配置环境变量" >&2
    exit 1
  fi
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "需要安装 uv：https://docs.astral.sh/uv/" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "需要安装 Node.js / npm" >&2
  exit 1
fi

echo "==> 同步后端依赖"
(cd backend && uv sync --extra dev)

echo "==> 安装前端依赖"
(cd frontend && npm install --silent)

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"

# 提示：本机开发需自行准备 PG/Redis（或 docker compose 起依赖）；启动 API 前建议迁移
echo "==> 提示：启动 API 前可执行：cd backend && uv run alembic upgrade head"
echo "    （不强制起 Docker PG；DATABASE_URL 见 .env）"

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "==> 启动后端 http://${API_HOST}:${API_PORT}"
(
  cd backend
  uv run uvicorn app.main:app --reload --host "$API_HOST" --port "$API_PORT"
) &
PIDS+=($!)

echo "==> 启动行情采集 python -m app.quote_collector"
(
  cd backend
  uv run python -m app.quote_collector
) &
PIDS+=($!)

echo "==> 启动 Ops ARQ worker（arq app.worker.settings.WorkerSettings）"
(
  cd backend
  uv run arq app.worker.settings.WorkerSettings
) &
PIDS+=($!)

# 等 API 文档端口就绪（最多约 15s）
for _ in $(seq 1 30); do
  code="$(curl -sf -o /dev/null -w "%{http_code}" "http://${API_HOST}:${API_PORT}/docs" || true)"
  if [[ "$code" == "200" ]]; then
    break
  fi
  sleep 0.5
done

echo "==> 启动前端 http://127.0.0.1:5173"
echo "    使用已有账号登录；Ctrl+C 结束 API / 采集 / ARQ worker / 前端"
(cd frontend && npm run dev -- --host 127.0.0.1 --port 5173) &
PIDS+=($!)

wait
