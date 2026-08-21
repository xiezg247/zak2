### Task 4: market + radar + emotion 拆壳

**Files 删除（27 个 shim）：**
- `app/services/market/` 整目录（`__init__.py` + bar_download/bars/db_ranks/fundamentals/limit_list_store/overview/quote_factor_patch/quote_notify_hub/quotes/seal_time/sector/stock_industry/suspend/tushare_client/tushare_screener.py）
- `app/services/radar/` 整目录（`__init__.py` + cards/radar_horizon/radar_predict/radar_resonance.py）
- `app/services/emotion/` 整目录（`__init__.py` + emotion_cycle/emotion_cycle_cache/emotion_hysteresis/emotion_thresholds.py）
- `app/schemas/market.py`
- `app/api/v1/market.py`

**改消费者（先改后删，全部机械前缀替换 `app.services.market`→`app.domains.market`、`app.services.radar`→`app.domains.radar`、`app.services.emotion`→`app.domains.emotion`、`app.schemas.market`→`app.domains.market.schemas`）：**

app 内（约 55 行）：
- `app/services/ops/`：sync_calendar/sync_universe/enrich_quotes/fill_focus_pool_minute/sync_watchlist_financials/prefetch_tushare/bars_fill/sync_suspend/sync_limit_list/sync_disclosure/scan_horizon_outlook（含 radar）/sync_stock_industry/warm_radar（含 schemas.market + radar）/health/prefetch_moneyflow/warm_market（emotion）/sync_sector
- `app/services/ai/`：ai_tools/ai_read_tools/ai_context
- `app/services/team/team_prefetch.py`（含函数内 lazy import）
- `app/services/strategy/strategy_board.py`
- `app/services/quote_collect/universe.py`
- `app/main.py`、`app/api/v1/ws.py`（quote_notify_hub）
- `app/api/v1/__init__.py`：market router 直连 `from app.domains.market.router import router as market_router`，从 `from app.api.v1 import (...)` 元组移除 market。

tests（约 89 行）：全部 `app.services.market|app.services.radar|app.services.emotion|app.schemas.market` → 对应 domains 路径。

**注意：**
- 前缀替换即可（`app.services.market.quotes` → `app.domains.market.quotes`，模块名不变；别名如 `as ts`/`as bars`/`as market` 不变）。
- `schemas.market` 的消费方（如 `from app.schemas.market import ...`）→ `from app.domains.market.schemas import ...`。
- 用 sed 类批量替换时小心不要误伤 `app/services/market` 目录本身（已删）。

**删除后残留扫描必须零命中：**
```bash
cd backend && rg "app.services.market|app.services.radar|app.services.emotion|app.schemas.market|app.api.v1.market" app tests --glob '*.py'
```

**测试：**
```bash
cd backend && uv run pytest -q --tb=short
```
全量绿才提交（预计 713+）。

**Commit**（简体中文 HEREDOC）：
`refactor(domains): 拆除 market/radar/emotion 域兼容壳`

**Report** → `/Users/xiezhigang/Projects/me/zak2/.worktrees/backend-domains-phase6/.superpowers/sdd/task-4-report.md`

**禁止：** 改 REST 路径/算法/ARQ job 名；改 domains 实现；删其它域 shim（backtest/watchlist/positions/signal_panel 属 Task 5/6）。
