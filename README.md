# zak2 — FastAPI + Vue 量化终端（Web）

zak 桌面端（PyQt）的 Web 重写版。**业务逻辑在本仓库独立实现**，与 zak **共用同一 PostgreSQL**（及可选 Redis），不依赖 `vnpy_*` 包。

Schema 主权仍在 zak Alembic；zak2 只读写同库。

## 能力概览

| 模块 | 路由 | 说明 |
|------|------|------|
| 登录 | `/login` | 兼容 zak `auth.users` |
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

与桌面差距见 [docs/gap-vs-desktop.md](docs/gap-vs-desktop.md)。

## 前置

1. 在 **zak** 侧完成 PG 迁移与用户：`uv run python cli.py db upgrade`
2. 复制环境变量：`cp .env.example .env` 并填写（建议配置 `TICKFLOW_API_KEY`）
3. （可选）若不用 zak2 collector，仍可用 zak CLI：`uv run python cli.py job run collect_quotes`（**勿与 collector 双写同一 Redis**）

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

# 另开：行情采集（TickFlow → Redis）
uv run python -m app.quote_collector
# 或 ./scripts/quote_collector.sh

cd frontend && npm install && npm run dev
```

打开 http://127.0.0.1:5173 ，使用 zak 已有账号登录。

## Docker Compose（api + web + quote-collector）

不编 PG/Redis：连**宿主机**上 zak 已有的库与 Redis（容器内用 `host.docker.internal`）。

```bash
cp -n .env.example .env   # 填 JWT_SECRET 等
docker compose up --build
```

- Web：http://127.0.0.1:8080  
- API：http://127.0.0.1:8000/docs  

Linux 已加 `extra_hosts: host.docker.internal:host-gateway`。请确保宿主机 Postgres/Redis 监听可被 Docker 访问（勿仅绑 `127.0.0.1` 若连不上则改监听或用 `DOCKER_DATABASE_URL` 覆盖）。

## 验收

```bash
./scripts/check.sh          # pytest + 前端 build
```

手工路径见 [docs/smoke-checklist.md](docs/smoke-checklist.md)。

要点：Web 跑一次选股 → `app.screener_runs` 有记录 → 桌面同用户历史可见。

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

上表为常用项；Ops 页可跑完整列表见 `backend/app/services/ops_catalog.py` 的 `RUNNABLE_JOB_IDS`。其余调度任务仍用 zak CLI：`job run <id>`。

## 文档

| 文档 | 内容 |
|------|------|
| [docs/architecture-p1.md](docs/architecture-p1.md) | 早期架构笔记 |
| [docs/gap-vs-desktop.md](docs/gap-vs-desktop.md) | 与桌面能力缺口 |
| [docs/smoke-checklist.md](docs/smoke-checklist.md) | 联调勾选清单 |

## 分期回顾

P1 登录+选股 → P2 自选/K 线 → P3 市场/板块/雷达 → P4 守则/笔记/信息流 → P5 回测 → P6 AI → P7 运维；其后加深选股 preset、自动选股、雷达龙头与工程收尾（本文档与脚本）。
