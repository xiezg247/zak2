# Task 4 Report: 拆除 market + radar + emotion 域兼容壳

## Status

DONE（Wave B Task 4 完成，全量回归绿，已提交）

## Commits

- `4819c3a` refactor(domains): 拆除 market/radar/emotion 域兼容壳（97 files changed, +427/−400）

## Changes

**删除（27 个 shim）：**
- `app/services/market/` 整目录（16 模块 + `__init__.py`）
- `app/services/radar/` 整目录（4 模块 + `__init__.py`）
- `app/services/emotion/` 整目录（4 模块 + `__init__.py`）
- `app/schemas/market.py`
- `app/api/v1/market.py`

**消费者替换（134 处，机械前缀替换，模块名/别名不变）：**
- `app/services/ops/`（17 文件）、`app/services/ai/`（3 文件）、`app/services/team/team_prefetch.py`（含函数内 lazy import）、`app/services/strategy/strategy_board.py`、`app/services/quote_collect/universe.py`、`app/main.py`、`app/api/v1/ws.py`
- `app/api/v1/__init__.py`：`market` 从 api.v1 元组移除，改为 `from app.domains.market.router import router as market_router` 直连
- tests（58 文件）：全部 `app.services.market|radar|emotion`、`app.schemas.market` 指向 domains

**映射：** `app.services.market`→`app.domains.market`、`app.services.radar`→`app.domains.radar`、`app.services.emotion`→`app.domains.emotion`、`app.schemas.market`→`app.domains.market.schemas`

## Verification

- 残留扫描零命中：`rg "app.services.market|app.services.radar|app.services.emotion|app.schemas.market|app.api.v1.market" app tests --glob '*.py'` → 无输出（exit 1）
- 全量回归：`uv run pytest -q --tb=short` → **713 passed**（与预期 713+ 一致）
- lint：`app/api/v1/__init__.py` 无错误

## Concerns

- 无功能风险：未改 REST 路径/算法/ARQ job 名；backtest/watchlist/positions/signal_panel 等其它域 shim 未动（属 Task 5/6）
- 顺带把此前未提交的 `.superpowers/sdd/`（task 1–4 brief/report）一并入库；如不想入库可后续移除
