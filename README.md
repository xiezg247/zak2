# zak2 — FastAPI + Vue 量化终端（Web）

独立 Web 量化终端。**业务逻辑在本仓库实现**，自带 PostgreSQL / Redis（Compose 或本地）；不依赖 zak 桌面运行时、`vnpy_*` 包或 zak CLI。

Schema 主权在本仓 **Alembic**（`backend/alembic/`）。

## 能力概览

| 模块 | 路由 | 说明 |
|------|------|------|
| 登录 | `/login` | JWT；兼容自 zak 导入的 `auth.users` |
| 守则 | `/playbook` | 章节 / 纪律 / 计划只读 |
| 自选 | `/watchlist` | CRUD、分组、蜡烛图、轮询 |
| 市场 / 板块 / 雷达 | `/market` `/sectors` `/radar` | 排行、资金、卡片 + 龙头跳转 |
| 选股 Hub | `/screener` | Preset / 配方 / 硬过滤 / 方案 / 历史 |
| 信息流 / 笔记 | `/feed` `/notes` | 只读时间线（Ops/定时可同步 B 站）；备忘流水 |
| 回测 | `/backtest` | 简化双均线 + 历史 |
| AI | `/ai` | 流式 + 只读 tool-calling |
| 运维 | `/ops` | 健康、调度开关、可跑 sync/选股 |

选股已实现 preset：涨幅/强势/换手/量比/成交量/自定义、涨停、低 PE、中大盘、主力净流入。  
配方：盘中多因子、极致短线、盘后多因子、**雷达龙头**。

产品路线与排期见 [docs/product-roadmap.md](docs/product-roadmap.md)。

## 前置

1. 复制环境变量：`cp .env.example .env` 并填写（建议配置 `TICKFLOW_API_KEY`）
2. 迁移数据库：`cd backend && uv sync --extra dev && uv run alembic upgrade head`
3. （可选）从旧 zak 库一次性导入用户/自选（目标库已 `alembic upgrade head` 后）：

```bash
ZAK_IMPORT_DATABASE_URL=postgresql+psycopg://zak:zak@localhost:5432/zak \
DATABASE_URL=postgresql+psycopg://zak2:zak2@localhost:5432/zak2 \
python scripts/import_from_zak.py --force
```

默认跳过日 K 大表；需同步 universe/日历等时加 `--with-market-sync-tables`。见 `.env.example` 中 `ZAK_IMPORT_DATABASE_URL`。

## 启动

```bash
# 一键（推荐：API + 行情采集 + 前端）
chmod +x scripts/dev.sh scripts/check.sh scripts/quote_collector.sh
./scripts/dev.sh
```

或分终端：

```bash
cd backend && uv sync --extra dev
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 另开：行情采集（TickFlow → Redis，键前缀 zak2:）
uv run python -m app.quote_collector
# 或 ./scripts/quote_collector.sh

cd frontend && npm install && npm run dev
```

打开 http://127.0.0.1:5173 ，使用已有账号登录（或导入后登录）。

## Docker Compose（postgres + redis + api + quote-collector + web）

自带 postgres / redis；API 容器启动前自动 `alembic upgrade head`。

```bash
cp -n .env.example .env   # 填 JWT_SECRET 等
docker compose up --build
```

- Web：http://127.0.0.1:8080  
- API：http://127.0.0.1:8001/docs（宿主机映射；容器内仍为 :8000）

宿主机端口占用时的映射（见 `docker-compose.yml`）：

| 宿主机 | 容器 |
|--------|------|
| 5433 | postgres 5432 |
| 6380 | redis 6379 |
| 8001 | api 8000 |

容器内服务 URL 不变（`postgres:5432`、`redis:6379`）。从宿主机直连 PG/Redis 时用 `postgresql+psycopg://zak2:zak2@127.0.0.1:5433/zak2`、`redis://127.0.0.1:6380/0`。

## 验收

```bash
./scripts/check.sh          # pytest + 前端 build
```

手工路径见 [docs/smoke-checklist.md](docs/smoke-checklist.md)。

要点：Web 跑一次选股 → `app.screener_runs` 有记录；（可选）从 zak 导入后可用原账号登录。

## 运维可跑 Job

| job_id | 说明 |
|--------|------|
| `purge_stale_cache` | 清理过期 cache |
| `sync_universe` | Tushare stock_basic → app.universe（A 股列表） |
| `sync_trade_calendar` | Tushare → 交易日历 |
| `sync_limit_list` | Tushare 涨停列表/封板时刻 |
| `sync_sector_flow_daily` | 板块资金日表 |
| `fill_watchlist_bars` | 补全自选日 K |
| `batch_fill_stale` | 全市场过期日 K 增量补全 |
| `batch_download_universe` | 全市场日 K 首下/补起点（单次上限） |
| `screen_intraday` | 盘中自动选股写历史 |
| `screen_post_close` | 盘后自动选股写历史 |
| `sync_bilibili_feed` | B 站动态 → feed_items（需 `BILIBILI_COOKIES`） |

上表为常用项；Ops 页可跑完整列表见 `backend/app/services/ops_catalog.py` 的 `RUNNABLE_JOB_IDS`。未实现项见 [docs/product-roadmap.md](docs/product-roadmap.md)。

## 文档

| 文档 | 内容 |
|------|------|
| [docs/product-roadmap.md](docs/product-roadmap.md) | 产品路线与排期 |
| [docs/architecture-p1.md](docs/architecture-p1.md) | 早期架构笔记 |
| [docs/archive/gap-vs-desktop.md](docs/archive/gap-vs-desktop.md) | 与桌面能力缺口（已归档） |
| [docs/smoke-checklist.md](docs/smoke-checklist.md) | 联调勾选清单 |

## 分期回顾

P1 登录+选股 → P2 自选/K 线 → P3 市场/板块/雷达 → P4 守则/笔记/信息流 → P5 回测 → P6 AI → P7 运维；其后加深选股 preset、自动选股、雷达龙头与独立演进收尾（本文档与脚本）。
