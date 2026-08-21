### Task 1: 修复 domains 内双路径漂移

**Files:**（14 个文件，全部在 `backend/app/domains/`）
- `watchlist/market_views.py`、`watchlist/enrich.py`
- `radar/radar_predict.py`、`radar/cards.py`
- `market/bars.py`、`market/fundamentals.py`
- `screener/engine.py`、`screener/reference_peer.py`、`screener/leader_screen.py`、`screener/pattern_screen.py`、`screener/hard_filters.py`、`screener/resonance_screen.py`
- `content/notes.py`、`content/notify_log.py`

**做法：** 将上述文件内的旧路径 import 全部改 `app.domains.*`（精确映射，用 `rg -n "app.services.market|app.services.radar|app.services.emotion|app.services.screener|app.repositories.watchlist|app.schemas.watchlist" backend/app/domains` 逐一核对）：

| 旧路径 | 新路径 |
|--------|--------|
| `app.services.market.quotes` | `app.domains.market.quotes` |
| `app.services.market.bars` | `app.domains.market.bars` |
| `app.services.market.fundamentals` | `app.domains.market.fundamentals` |
| `app.services.market.suspend` | `app.domains.market.suspend` |
| `app.services.market.stock_industry` | `app.domains.market.stock_industry` |
| `app.services.market.overview` | `app.domains.market.overview` |
| `app.services.market.seal_time` | `app.domains.market.seal_time` |
| `app.services.market.limit_list_store` | `app.domains.market.limit_list_store` |
| `app.services.market.tushare_client` | `app.domains.market.tushare_client` |
| `app.services.market.tushare_screener` | `app.domains.market.tushare_screener` |
| `app.services.radar.cards` | `app.domains.radar.cards` |
| `app.services.radar.radar_resonance` | `app.domains.radar.radar_resonance` |
| `app.services.emotion.emotion_cycle` | `app.domains.emotion.emotion_cycle` |
| `app.services.screener.leader_screen` | `app.domains.screener.leader_screen` |
| `app.repositories.watchlist` | `app.domains.watchlist.repository` |
| `app.schemas.watchlist` | `app.domains.watchlist.schemas` |

**注意：**
- `radar/cards.py:216` 的 lazy import `from app.services.screener import leader_screen` 也改（函数体内），改为 `from app.domains.screener import leader_screen`。
- 只改 import 行，不改任何逻辑/函数体。
- 改完后 `rg "app.services.|app.repositories.|app.schemas." backend/app/domains` 必须零命中（可排除 README.md 等文档）。

**验收：**
```bash
cd backend && uv run pytest -q --tb=short
```
全量绿才提交。

**Commit**（简体中文 HEREDOC）：
`refactor(domains): 域内旧路径引用全部改走 app.domains`

**Report** → `/Users/xiezhigang/Projects/me/zak2/.worktrees/backend-domains-phase6/.superpowers/sdd/task-1-report.md`（Status、Commits、Tests 结果、Concerns）

**禁止：** 删 shim（Task 2 起才删）；改旧路径 shim 文件；改逻辑。
