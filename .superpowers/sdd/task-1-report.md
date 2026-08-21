# Task 1 Report: 修复 domains 内双路径漂移

## Status
✅ Done

## Commits
- `d2c601c` `refactor(domains): 域内旧路径引用全部改走 app.domains`（14 文件，35 增 35 删，纯 import 行替换，无逻辑改动）

## Changes
按 brief 映射表替换 14 个文件的旧路径 import：
- `app.services.market.*` → `app.domains.market.*`（quotes/bars/fundamentals/suspend/stock_industry/overview/seal_time/limit_list_store/tushare_client/tushare_screener）
- `app.services.radar.cards|radar_resonance` → `app.domains.radar.*`
- `app.services.emotion.emotion_cycle` → `app.domains.emotion.emotion_cycle`
- `app.services.screener.leader_screen` → `app.domains.screener.leader_screen`（含 `radar/cards.py:216` lazy import）
- `app.repositories.watchlist` → `app.domains.watchlist.repository`（resolve_symbol_pair）
- `app.schemas.watchlist` → `app.domains.watchlist.schemas`（BarOut/BarsResponse/DisclosureOut/FinancialSnapshotOut/FinancialSyncOut/FundamentalsOut/NotifyLogItem/NotifyLogOut）

## Tests
`cd backend && uv run pytest -q --tb=short` → **713 passed in 7.91s**

## Verify
- 窄正则（映射表旧路径）`rg "app.services.market|app.services.radar|app.services.emotion|app.services.screener|app.repositories.watchlist|app.schemas.watchlist" backend/app/domains` → **零命中** ✅
- 宽正则 `rg "app.services.|app.repositories.|app.schemas." backend/app/domains` 仍有命中，均为范围外合法引用：
  - `app.services.symbols`、`app.repositories.pagination/base`（保留的真实现/横切，永不删）
  - `app.schemas.market`（leader_screen.py:12、resonance_screen.py:11，Task 4 拆壳范围）
  - 其余文件（channels/backtest/auto_schedules 等）的 `app.schemas.common/ops/screener`、`app.services.ops.*` 等，属后续 Task 范围

## Concerns
1. 宽正则「零命中」在本 Task 范围内**不可达**：plan 中 `app.services.symbols`、`app.repositories.{base,pagination}` 为保留真实现，`app.schemas.market` 属 Task 4。建议全局零命中验收以 Task 7 为准（届时 schemas.market/screener/ops 等拆完，仅剩真实现）。
2. 未删除任何 shim（符合 Task 1 约束，Task 2 起删）。
