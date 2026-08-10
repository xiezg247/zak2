#!/usr/bin/env bash
# 构建并启动 api + web（PG/Redis 用宿主机）
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
