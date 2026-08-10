# Docker Compose（方案 A：仅 api + web）

日期：2026-08-06  
状态：已批准

## 范围

- 服务：`api`（FastAPI）、`web`（nginx 静态 + 反代 `/api`）
- PG / Redis：**不**编入 Compose，使用宿主机 zak 实例
- 容器内通过 `host.docker.internal` 访问宿主机 `5432` / `6379`

## 非目标

自带 postgres/redis 镜像、Alembic 迁库、改 zak。
