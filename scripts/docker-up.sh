#!/usr/bin/env bash
# 构建并启动 compose：自带 postgres + redis + api + arq-worker + quote-collector + web
# api 入口会先 alembic upgrade head；宿主机端口见 docker-compose.yml（常为 5433/6380）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "已生成 .env，请检查 JWT_SECRET 等后再用"
  else
    echo "缺少 .env" >&2
    exit 1
  fi
fi

docker compose up --build "$@"
