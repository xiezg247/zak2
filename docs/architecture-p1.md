# zak2 架构（P1）

## 决策摘要

| 项 | 选择 |
|----|------|
| 目标 | 以 [product-roadmap.md](./product-roadmap.md) 为准，非全量对齐桌面 |
| 复用 | 自有 PostgreSQL / Redis；业务在本仓；不 import `vnpy_*` |
| 结构 | `backend/` FastAPI + `frontend/` Vue3；后端业务域渐进迁入 `app/domains/`（见 [backend-architecture-refactor-design](./superpowers/specs/2026-08-20-backend-architecture-refactor-design.md)） |
| Schema | zak2 Alembic（`backend/alembic/`） |

## 运行时

```text
Vue SPA ──JWT REST──▶ FastAPI ──▶ PostgreSQL（zak2 自有库）
                         │
                         ├── Redis（行情快照，键前缀 zak2:）
                         └── Tushare（财务 preset，可选）
```

## 鉴权

- 表：`auth.users`
- 密码：`pbkdf2_sha256$salt$hex`（120000 次），与 zak 兼容
- Token：JWT HS256，前端 `localStorage.zak_access_token`

## P1 API

- `POST /api/v1/auth/login`、`GET /api/v1/auth/me`
- `/api/v1/screener/*`（presets、hard-filter-templates、schemes、recipes、runs）
- `/api/v1/jobs/*`

## P2 API

- `/api/v1/watchlist` CRUD、分组
- `GET /api/v1/quotes`、`GET /api/v1/bars/{vt_symbol}`

## P3 API

- `GET /api/v1/market/overview`、`/market/ranks`
- `GET /api/v1/sectors/dates`、`/sectors/flow`、`/sectors/flow/{id}/intraday`
- `GET /api/v1/radar/cards`

## P4 API

- `/api/v1/playbook/sections`、`/discipline`、`/plans`
- `/api/v1/notes/*`
- `/api/v1/feed/subscriptions`、`/feed/items`

## P5 API

- `/api/v1/backtest/strategies`、`/profiles`、`/runs`、`/batches`
- `POST /api/v1/backtest/runs`、`/runs/batch`

## P6 API

- `/api/v1/ai/status`、`/sessions`、`/sessions/{id}/messages`
- `POST .../chat`、`.../chat/stream`（SSE；`use_tools` 默认 true）
- 工具：`get_watchlist` / `get_market_emotion` / `get_recent_screening` / `get_radar_snapshot` / `get_bars_summary` / `get_recent_backtest`

## P7 API

- `GET /api/v1/ops/health`
- `GET /api/v1/ops/bars/overview`
- `GET|PUT /api/v1/ops/scheduler/config`
- `GET /api/v1/ops/scheduler/jobs`、`PATCH .../jobs/{id}`
- `POST .../jobs/{id}/run`（含 `screen_intraday` / `screen_post_close`）
- `POST /api/v1/ops/cache/purge`、`/sync/trade-calendar`、`/sync/sector-flow`、`/sync/screen-intraday`

## 分期

P1–P7 已做（运维加深：日历 + 板块资金 sync + 日 K overview）
