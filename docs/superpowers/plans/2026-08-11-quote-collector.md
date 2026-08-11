# zak2 独立行情采集（Quote Collector）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 独立 `quote-collector` 进程用 TickFlow 拉全市场快照写入 Redis（键兼容现网），Ops 展示心跳并可强制采一轮；Web 不再依赖 zak CLI `collect_quotes`。

**Architecture:** Collector 进程：`universe → TickFlowProvider → RedisQuoteWriter → PUBLISH notify`；API 只读 heartbeat / 发 `force` cmd。不把全市场采集加入 `RUNNABLE_JOB_IDS`。

**Tech Stack:** FastAPI、redis-py、官方 `tickflow` 包、Vue OpsView、pytest mock。

**Spec:** `docs/superpowers/specs/2026-08-11-quote-collector-design.md`

## Global Constraints

- 只改 zak2；不改 zak；不 import `vnpy_*`
- 不把全市场采集塞进 uvicorn / 内嵌 APScheduler
- Redis 键前缀保持 `zak`；始终 `PUBLISH zak:notify:quotes`
- 同一 Redis 不与 zak 采集双写（文档约定）
- 本刀不做 Tushare enrich / `change_speed_5m` / L1 cache
- Commit 仅用户明确要求时（默认跳过）
- 单测全部 mock，不打真 TickFlow / 真 Redis

**Clarifications:**

- 默认 Provider：`tickflow`（PyPI `tickflow[all]>=0.1.22` 进主依赖）
- HASH 写长 field；空 quotes 不 incr / 不 publish
- 交易时段：工作日 `09:15–11:30` / `13:00–15:05` Asia/Shanghai；`force` 可越时段
- Heartbeat key：`zak2:collector:heartbeat` EX=120；新鲜阈值 90s
- Cmd channel：`zak2:collector:cmd`，payload `force`

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/quote_collect/__init__.py` | 包导出 |
| `backend/app/services/quote_collect/models.py` | `QuoteSnapshot` |
| `backend/app/services/quote_collect/session.py` | 交易时段判断 |
| `backend/app/services/quote_collect/writer.py` | `RedisQuoteWriter` |
| `backend/app/services/quote_collect/provider.py` | Protocol + `TickFlowProvider` + `get_provider` |
| `backend/app/services/quote_collect/universe.py` | 读 `app.universe` → TF symbols |
| `backend/app/services/quote_collect/heartbeat.py` | 读写 heartbeat / 新鲜判定 |
| `backend/app/services/quote_collect/control.py` | cmd pub/sub helper |
| `backend/app/services/quote_collect/loop.py` | `collect_once` / `run_forever` |
| `backend/app/quote_collector.py` | `python -m app.quote_collector` 入口 |
| `backend/app/integrations/tickflow/__init__.py` | 薄导出 |
| `backend/app/integrations/tickflow/client.py` | `get_tickflow_client` |
| `backend/tests/test_quote_collect_writer.py` | Writer 单测 |
| `backend/tests/test_quote_collect_session.py` | 时段单测 |
| `backend/tests/test_quote_collect_provider.py` | 解析 / provider 单测 |
| `backend/tests/test_quote_collect_loop.py` | once / force / skip |
| `backend/tests/test_ops_quote_collector.py` | health + force API |
| `backend/app/core/settings.py` | collector 相关 settings |
| `backend/app/services/ops_health.py` / `schemas/ops.py` | `quote_collector` |
| `backend/app/api/v1/ops.py` | `POST .../collector/force` |
| `backend/app/services/ops_scheduler.py` | `collect_quotes` run_hint |
| `backend/pyproject.toml` (+ lock) | `tickflow` 依赖 |
| `.env.example` / `docker-compose.yml` / `scripts/` | 配置与启动 |
| `frontend/src/api/ops.ts` / `OpsView.vue` | UI |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` / `README.md` | 文档 |

---

### Task 1: QuoteSnapshot + 交易时段 + RedisWriter

**Files:**
- Create: `backend/app/services/quote_collect/__init__.py`
- Create: `backend/app/services/quote_collect/models.py`
- Create: `backend/app/services/quote_collect/session.py`
- Create: `backend/app/services/quote_collect/writer.py`
- Create: `backend/tests/test_quote_collect_session.py`
- Create: `backend/tests/test_quote_collect_writer.py`

**Interfaces:**
- `QuoteSnapshot` dataclass：spec 字段，默认 0 / `""`
- `is_ashare_trading_session(now: datetime | None = None) -> bool` — tz-aware 或 naive 按 Asia/Shanghai
- `RedisQuoteWriter(client)`：
  - `KEY_PREFIX = "zak"`
  - `QUOTE_KEY_FMT` / `RANK_KEY_FMT` / `META_*` / `NOTIFY_CHANNEL = "zak:notify:quotes"`
  - `FULL_RANK_FIELDS = ("change_pct","turnover_rate","amount","volume","amplitude")`
  - `write_quotes(quotes: dict[str, QuoteSnapshot]) -> int` — 空 → 0；否则 incr seq、hset、zadd 重建榜、meta、publish
- `snapshot_to_hash(q: QuoteSnapshot) -> dict[str, str]` — 长 field，数值 `str`

- [ ] **Step 1: 写失败单测（时段）**

```python
# backend/tests/test_quote_collect_session.py
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.quote_collect.session import is_ashare_trading_session

TZ = ZoneInfo("Asia/Shanghai")

def test_morning_open() -> None:
    assert is_ashare_trading_session(datetime(2026, 8, 11, 9, 30, tzinfo=TZ))  # Tue

def test_lunch_skip() -> None:
    assert not is_ashare_trading_session(datetime(2026, 8, 11, 12, 0, tzinfo=TZ))

def test_weekend_skip() -> None:
    assert not is_ashare_trading_session(datetime(2026, 8, 8, 10, 0, tzinfo=TZ))  # Sat

def test_afternoon_edge() -> None:
    assert is_ashare_trading_session(datetime(2026, 8, 11, 15, 0, tzinfo=TZ))
    assert not is_ashare_trading_session(datetime(2026, 8, 11, 15, 6, tzinfo=TZ))
```

- [ ] **Step 2: 跑时段测确认失败**

Run: `cd backend && uv run pytest tests/test_quote_collect_session.py -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 session + models**

```python
# models.py — @dataclass slots=True QuoteSnapshot with defaults
# session.py — weekday < 5；time in [09:15,11:30] or [13:00,15:05]
```

- [ ] **Step 4: 写 Writer 失败单测**

```python
# backend/tests/test_quote_collect_writer.py
from unittest.mock import MagicMock

from app.services.quote_collect.models import QuoteSnapshot
from app.services.quote_collect.writer import RedisQuoteWriter

def test_write_empty_noop() -> None:
    client = MagicMock()
    assert RedisQuoteWriter(client).write_quotes({}) == 0
    client.pipeline.assert_not_called()
    client.publish.assert_not_called()

def test_write_quotes_pipeline_and_publish() -> None:
    client = MagicMock()
    pipe = MagicMock()
    client.pipeline.return_value = pipe
    pipe.execute.return_value = [7]  # seq from incr
    q = QuoteSnapshot(symbol="SHSE.600519", name="茅台", last_price=100.0, change_pct=1.5, amount=1e9)
    n = RedisQuoteWriter(client).write_quotes({"SHSE.600519": q})
    assert n == 1
    pipe.incr.assert_called()  # or assert call args contain meta:seq
    client.publish.assert_called_with("zak:notify:quotes", "7")
```

实现 Writer 时：pipeline 内 `incr` 必须是**第一条**命令，以便 `execute()[0]` 为 seq（与桌面一致）。主榜：对每个 `FULL_RANK_FIELDS` 先 `delete` 再批量 `zadd`（或 `zadd` 全量后删不在成员——本刀用 delete+zadd 全量重建）。稀疏榜仅当 `volume_ratio>0` / `net_mf_amount!=0` / `limit_times>=1` 时写入对应成员（本刀可不 delete 稀疏榜旧成员，YAGNI；或对稀疏榜同样 delete+zadd 仅含有效成员——**写死：稀疏榜每轮 delete 键后只 zadd 本轮有效成员**）。

- [ ] **Step 5: 跑 Writer 测确认失败 → 实现 writer → 再跑通过**

Run: `cd backend && uv run pytest tests/test_quote_collect_session.py tests/test_quote_collect_writer.py -v`  
Expected: PASS

- [ ] **Step 6: Commit（默认跳过）**

---

### Task 2: TickFlow client + Provider

**Files:**
- Create: `backend/app/integrations/tickflow/__init__.py`
- Create: `backend/app/integrations/tickflow/client.py`
- Create: `backend/app/services/quote_collect/provider.py`
- Create: `backend/tests/test_quote_collect_provider.py`
- Modify: `backend/pyproject.toml`（依赖）
- Run: `cd backend && uv lock`（更新 lock）

**Interfaces:**
- `get_tickflow_client(*, api_key: str = "") -> Any` — 有 key → `TickFlow(api_key=key)`；否则 `TickFlow.free()`
- `parse_tickflow_row(row: dict) -> QuoteSnapshot` — `ext.change_pct` 等为小数时 ×100（与 zak `parse_quote_row` 一致）
- `class QuoteProvider(Protocol): name: str; def fetch(self, symbols: list[str]) -> dict[str, QuoteSnapshot]: ...`
- `class TickFlowProvider:`  
  - `name = "tickflow"`  
  - `BATCH=80`；workers 从 env `QUOTE_FETCH_MAX_WORKERS` 夹逼 1–8，默认 4  
  - `fetch`：按批调用 `client.quotes.get(symbols=..., as_dataframe=True)`，解析合并  
- `get_provider(name: str | None = None) -> QuoteProvider` — 仅 `"tickflow"`；其它 → `ValueError`

- [ ] **Step 1: 写解析单测**

```python
# backend/tests/test_quote_collect_provider.py
from app.services.quote_collect.provider import parse_tickflow_row, get_provider

def test_parse_change_pct_scale() -> None:
    q = parse_tickflow_row({
        "symbol": "SHSE.600519",
        "name": "茅台",
        "last_price": 1800,
        "prev_close": 1780,
        "open": 1785,
        "high": 1810,
        "low": 1770,
        "volume": 1e6,
        "amount": 1e9,
        "ext.change_pct": 0.0112,
        "ext.change_amount": 20,
        "ext.turnover_rate": 0.01,
        "ext.amplitude": 0.02,
    })
    assert q.symbol == "SHSE.600519"
    assert abs(q.change_pct - 1.12) < 1e-6
    assert abs(q.turnover_rate - 1.0) < 1e-6
    assert abs(q.amplitude - 2.0) < 1e-6

def test_get_provider_tickflow() -> None:
    assert get_provider("tickflow").name == "tickflow"

def test_get_provider_unknown() -> None:
    import pytest
    with pytest.raises(ValueError):
        get_provider("nope")
```

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && uv run pytest tests/test_quote_collect_provider.py -v`  
Expected: FAIL

- [ ] **Step 3: pyproject 加依赖并 lock**

```toml
# backend/pyproject.toml dependencies 增加：
"tickflow[all]>=0.1.22",
```

Run: `cd backend && uv lock && uv sync --extra dev`

- [ ] **Step 4: 实现 client + provider（含 mockable fetch 测可选）**

`fetch` 内可用 `concurrent.futures.ThreadPoolExecutor` 做 batch；单测可不测并发，另加：

```python
def test_fetch_batches(monkeypatch) -> None:
    from app.services.quote_collect import provider as p
    calls: list[list[str]] = []
    class FakeQuotes:
        def get(self, symbols, as_dataframe=True):
            calls.append(list(symbols))
            import pandas as pd
            return pd.DataFrame([{"symbol": symbols[0], "last_price": 1.0, "ext.change_pct": 0.01}])
    class FakeClient:
        quotes = FakeQuotes()
    monkeypatch.setattr(p, "get_tickflow_client", lambda api_key="": FakeClient())
    monkeypatch.setenv("QUOTE_FETCH_MAX_WORKERS", "1")
    out = p.TickFlowProvider(api_key="x").fetch(["SHSE.600000", "SHSE.600001"])
    # BATCH=80 时两只在一批；若测多分批可传 >80 只
    assert "SHSE.600000" in out
```

若引入 pandas 仅因 TickFlow dataframe：依赖已由 `tickflow[all]` 带入；解析路径同时支持 `iterrows` 与 list[dict]。

- [ ] **Step 5: 跑测通过**

Run: `cd backend && uv run pytest tests/test_quote_collect_provider.py -v`  
Expected: PASS

- [ ] **Step 6: Commit（默认跳过）**

---

### Task 3: Universe + heartbeat + control + collect_once

**Files:**
- Create: `backend/app/services/quote_collect/universe.py`
- Create: `backend/app/services/quote_collect/heartbeat.py`
- Create: `backend/app/services/quote_collect/control.py`
- Create: `backend/app/services/quote_collect/loop.py`
- Create: `backend/tests/test_quote_collect_loop.py`

**Interfaces:**
- `load_tf_symbols(db: Session) -> list[str]` — `list_universe_symbols` + `to_tf_symbol`；保序去重
- Constants：`HEARTBEAT_KEY = "zak2:collector:heartbeat"`、`HEARTBEAT_TTL = 120`、`HEARTBEAT_FRESH_SEC = 90`、`CMD_CHANNEL = "zak2:collector:cmd"`
- `write_heartbeat(client, payload: dict) -> None` — `SET` JSON + EX
- `read_heartbeat(client) -> dict | None`
- `is_heartbeat_fresh(payload: dict | None, *, now: datetime | None = None) -> bool` — 解析 `ts` ISO，差 < 90s
- `publish_force(client) -> None` — `PUBLISH CMD_CHANNEL "force"`
- `collect_once(*, db, writer, provider, client, *, force: bool = False, now=None) -> dict`  
  返回 `{success, skipped, message, count}`：  
  - 非交易且非 force → skipped，heartbeat status=`skipped`  
  - universe 空 → skipped「请先 sync_universe」  
  - fetch+write；异常 → success=False，heartbeat status=`error`，`last_error`  
  - 成功 → status=`idle`（或 collecting 后 idle）

`run_forever` 可在 Task 4 完善；本刀 Task 3 至少实现 `collect_once` + 单测。

- [ ] **Step 1: 写 loop 单测**

```python
# backend/tests/test_quote_collect_loop.py
from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from app.services.quote_collect.loop import collect_once
from app.services.quote_collect.models import QuoteSnapshot

TZ = ZoneInfo("Asia/Shanghai")

def test_skip_off_hours() -> None:
    db, writer, provider, client = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    out = collect_once(
        db=db, writer=writer, provider=provider, client=client,
        force=False, now=datetime(2026, 8, 11, 12, 0, tzinfo=TZ),
    )
    assert out["skipped"] is True
    provider.fetch.assert_not_called()

def test_force_off_hours_collects(monkeypatch) -> None:
    from app.services.quote_collect import loop as loop_mod
    monkeypatch.setattr(loop_mod, "load_tf_symbols", lambda db: ["SHSE.600519"])
    db, client = MagicMock(), MagicMock()
    writer = MagicMock()
    writer.write_quotes.return_value = 1
    provider = MagicMock()
    provider.name = "tickflow"
    provider.fetch.return_value = {"SHSE.600519": QuoteSnapshot(symbol="SHSE.600519", last_price=1.0)}
    out = collect_once(
        db=db, writer=writer, provider=provider, client=client,
        force=True, now=datetime(2026, 8, 11, 12, 0, tzinfo=TZ),
    )
    assert out["skipped"] is False
    assert out["count"] == 1
    provider.fetch.assert_called_once()
```

- [ ] **Step 2: 实现 universe / heartbeat / control / collect_once → 测通过**

Run: `cd backend && uv run pytest tests/test_quote_collect_loop.py -v`  
Expected: PASS

- [ ] **Step 3: Commit（默认跳过）**

---

### Task 4: 主循环入口 + Settings

**Files:**
- Create: `backend/app/quote_collector.py`（`python -m app.quote_collector`）
- Modify: `backend/app/services/quote_collect/loop.py`（补 `run_forever`）
- Modify: `backend/app/core/settings.py`
- Modify: `.env.example`
- Create: `scripts/quote_collector.sh`

**Interfaces:**
- Settings 字段：
  - `quote_collector_enabled: bool = True`（env `QUOTE_COLLECTOR_ENABLED`）
  - `quote_collect_interval_sec: int = 30`（夹逼在 loop 内 5–300）
  - `quote_provider: str = "tickflow"`
  - `tickflow_api_key: str = ""`
- `run_forever()`：
  1. 建 redis client、`SessionLocal`、provider、writer  
  2. 后台线程 `pubsub.subscribe(CMD_CHANNEL)`：收到 `force` 设 `threading.Event`  
  3. 循环：若 disabled → exit 0；写 heartbeat；若 force event 或交易时段则 `collect_once`；clear force；`sleep(interval)`；异常记日志+heartbeat error，backoff ≤60s  
- `__main__`：logging basicConfig → `run_forever()`
- `scripts/quote_collector.sh`：`cd backend && uv run python -m app.quote_collector`

- [ ] **Step 1: 实现 settings + run_forever + 入口脚本**

注意：`app/quote_collector.py` 需可被 `-m app.quote_collector` 加载（包内模块；确保 `app` 为 package）。若 hatch 只打包 `app`，OK。

- [ ] **Step 2: 手测导入**

Run: `cd backend && uv run python -c "from app.services.quote_collect.loop import run_forever; from app.core.settings import get_settings; print(get_settings().quote_provider)"`  
Expected: 打印 `tickflow`

- [ ] **Step 3: `.env.example` 追加**

```bash
# 行情采集进程（python -m app.quote_collector）；与 zak CLI collect_quotes 互斥
TICKFLOW_API_KEY=
QUOTE_PROVIDER=tickflow
QUOTE_COLLECT_INTERVAL_SEC=30
QUOTE_COLLECTOR_ENABLED=true
# QUOTE_FETCH_MAX_WORKERS=4
```

- [ ] **Step 4: Commit（默认跳过）**

---

### Task 5: Ops health + force API + run_hint

**Files:**
- Modify: `backend/app/services/quote_collect/heartbeat.py`（若需 `snapshot_for_health`）
- Modify: `backend/app/services/ops_health.py`
- Modify: `backend/app/schemas/ops.py` — `HealthOut` 增加 `quote_collector: dict`
- Modify: `backend/app/api/v1/ops.py` — `POST /collector/force`
- Modify: `backend/app/services/ops_scheduler.py` — `collect_quotes` 的 `run_hint`
- Create: `backend/tests/test_ops_quote_collector.py`

**Interfaces:**
- `collector_health(client | None) -> dict`：`running` / `provider` / `status` / `last_count` / `ts` / `hint`
- `force_collect(client) -> dict`：`{success, message}` — 无新鲜 heartbeat → `success=False`，文案含 `python -m app.quote_collector`；有则 publish force，`success=True`
- `HealthOut.quote_collector: dict[str, Any] = Field(default_factory=dict)`
- `ops_scheduler`：非 runnable 时，若 `job_id == "collect_quotes"`：  
  `run_hint = "请启动 zak2：python -m app.quote_collector（勿与 zak CLI 双写）"`  
  其它 job 仍 `请用 zak CLI：job run ...`
- **禁止**把 `collect_quotes` 加入 `RUNNABLE_JOB_IDS`

- [ ] **Step 1: 写 API/健康单测**

```python
# backend/tests/test_ops_quote_collector.py
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.services.quote_collect.heartbeat import is_heartbeat_fresh
from app.services import ops_health
from app.services.quote_collect import control

def test_heartbeat_fresh() -> None:
    ts = datetime.now(timezone.utc).isoformat()
    assert is_heartbeat_fresh({"ts": ts})
    old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    assert not is_heartbeat_fresh({"ts": old})

def test_force_without_collector() -> None:
    client = MagicMock()
    with patch("app.services.quote_collect.control.read_heartbeat", return_value=None):
        # 若 force_collect 在 control 或独立 ops 模块：
        from app.services.quote_collect.control import force_collect
        out = force_collect(client)
    assert out["success"] is False
    assert "quote_collector" in out["message"] or "collector" in out["message"].lower()

def test_force_with_fresh_heartbeat() -> None:
    client = MagicMock()
    hb = {"ts": datetime.now(timezone.utc).isoformat(), "status": "idle"}
    with patch("app.services.quote_collect.control.read_heartbeat", return_value=hb):
        from app.services.quote_collect.control import force_collect
        out = force_collect(client)
    assert out["success"] is True
    client.publish.assert_called()
```

（实现时把 `force_collect` / `read_heartbeat` 放在 `control.py` 或 `heartbeat.py`，单测 import 路径与实现一致。）

- [ ] **Step 2: 实现 health / force / schema / route / run_hint**

```python
# ops.py
@router.post("/collector/force", response_model=SyncResult)
def collector_force(_user: User = Depends(get_current_user)) -> SyncResult:
    ...
```

- [ ] **Step 3: 跑测**

Run: `cd backend && uv run pytest tests/test_ops_quote_collector.py tests/test_quote_collect_loop.py -v`  
Expected: PASS

- [ ] **Step 4: Commit（默认跳过）**

---

### Task 6: 前端 + Compose + 文档

**Files:**
- Modify: `frontend/src/api/ops.ts`
- Modify: `frontend/src/views/OpsView.vue`
- Modify: `docker-compose.yml`
- Modify: `scripts/dev.sh`（可选启动 collector；或仅 echo 提示）
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`
- Modify: `README.md`

**Interfaces / UI:**
- `Health.quote_collector?: { running?: boolean; provider?: string; status?: string; last_count?: number; hint?: string; ts?: string }`
- `opsApi.forceCollector: () => api<SyncResult>('/api/v1/ops/collector/force', { method: 'POST' })`
- Ops 健康卡片「行情采集」：`running` 绿/红；展示 provider/status/last_count；按钮「强制采一轮」
- `docker-compose.yml` 增加：

```yaml
  quote-collector:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env
    environment:
      DATABASE_URL: ${DOCKER_DATABASE_URL:-postgresql+psycopg://zak:zak@host.docker.internal:5432/zak}
      REDIS_URL: ${DOCKER_REDIS_URL:-redis://host.docker.internal:6379/0}
    command: ["python", "-m", "app.quote_collector"]
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
```

- `dev.sh`：在 API 起来后额外后台启动 collector（可用 env `DEV_START_QUOTE_COLLECTOR=1` 默认 true 或 false——**写死默认启动** collector，与「独立演进」一致；Ctrl+C 一并清理）
- gap：行情采集常驻 → **有（薄）**；建议下一刀：Tushare enrich 或只读持仓/信号
- smoke：collector 启动 / Ops 心跳 / force / 行情可读
- README：启动含 collector；zak CLI 采集改为可选兼容说明

- [ ] **Step 1: 改前端类型与 OpsView**

- [ ] **Step 2: compose + dev.sh + 文档**

- [ ] **Step 3: 验证**

Run:
```bash
cd backend && uv run pytest tests/test_quote_collect_session.py tests/test_quote_collect_writer.py tests/test_quote_collect_provider.py tests/test_quote_collect_loop.py tests/test_ops_quote_collector.py -v
cd frontend && npm run build
```
Expected: 全绿

- [ ] **Step 4: Commit（默认跳过）**

---

## Spec coverage（自检）

| Spec 项 | Task |
|---------|------|
| 独立进程 + TickFlow Provider | 2–4 |
| Redis 长 field + rank + notify | 1 |
| Universe from PG | 3 |
| 交易时段 + force | 1, 3 |
| Heartbeat / cmd | 3–5 |
| Ops health + force API | 5–6 |
| 不进 RUNNABLE | 5 |
| run_hint 改指向 zak2 | 5 |
| compose service | 6 |
| gap / smoke / README | 6 |
| 无 enrich / 无 vnpy | Global |

## 验收对照

1. API + collector（无 zak CLI）→ Redis `quote_count>0`（需有效 TickFlow + universe）  
2. notify seq 递增 → WS/轮询刷新  
3. Ops force：有/无 collector 文案正确  
4. pytest 子集 + `npm run build` 绿  
