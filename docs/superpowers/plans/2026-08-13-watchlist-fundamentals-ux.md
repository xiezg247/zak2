# 自选详情基本面（财报+披露）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自选详情只读展示最近一期财报 snapshot 与最多 3 条披露记录，空态引导 Ops。

**Architecture:** 新建 `fundamentals.get_fundamentals` 读 `financial_snapshots` / `financial_sync_meta` / `disclosure_calendar`；`GET /watchlist/items/{vt}/fundamentals`；Watchlist 右侧日 K 下折叠卡片。

**Tech Stack:** FastAPI · SQLAlchemy text/select · Pydantic · Vue 3 · pytest

**Spec:** `docs/superpowers/specs/2026-08-13-watchlist-fundamentals-ux-design.md`

## Global Constraints

- 只读；不改 Ops job / strategy-board / 列表列
- 非法 vt → 400；空数据 200 空结构合法
- snapshot 最新 1 行；disclosures ≤3、`end_date DESC`
- 营收/净利 ≥1e8 显示「x.xx 亿」；比率 ×100 一位小数；日期 `YYYYMMDD`→`YYYY-MM-DD`
- Commit 简体中文；不 push

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/fundamentals.py` | `get_fundamentals` |
| `backend/app/schemas/watchlist.py` | Fundamentals* Out |
| `backend/app/api/v1/watchlist.py` | GET 路由 |
| `backend/tests/test_fundamentals.py` | 服务 + API 测 |
| `frontend/src/api/watchlist.ts` | `fundamentals(vt)` |
| `frontend/src/views/WatchlistView.vue` | 基本面卡片 |
| `docs/product-roadmap.md` / `docs/smoke-checklist.md` | 文档 |

---

### Task 1: fundamentals 服务 + 单测

**Files:**
- Create: `backend/app/services/fundamentals.py`
- Create: `backend/tests/test_fundamentals.py`

**Interfaces:**
- Produces: `get_fundamentals(db: Session, vt_symbol: str) -> dict`  
  keys: `vt_symbol`, `ts_code`, `snapshot`, `sync`, `disclosures`

- [ ] **Step 1: 写失败测**

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services import fundamentals as fund


def test_invalid_vt_400() -> None:
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        fund.get_fundamentals(db, "")
    assert ei.value.status_code == 400


def test_empty_db_returns_nulls() -> None:
    db = MagicMock()
    # execute 三次：snapshot / sync / disclosures 均无
    db.execute.return_value = MagicMock(mappings=MagicMock(first=MagicMock(return_value=None), all=MagicMock(return_value=[])))
    # 简化：side_effect 三个结果
    snap = MagicMock()
    snap.mappings.return_value.first.return_value = None
    meta = MagicMock()
    meta.mappings.return_value.first.return_value = None
    disc = MagicMock()
    disc.mappings.return_value.all.return_value = []
    db.execute.side_effect = [snap, meta, disc]
    out = fund.get_fundamentals(db, "600519.SSE")
    assert out["vt_symbol"] == "600519.SSE"
    assert out["ts_code"] == "600519.SH"
    assert out["snapshot"] is None
    assert out["sync"] is None
    assert out["disclosures"] == []


def test_snapshot_and_disclosures_mapped() -> None:
    db = MagicMock()
    snap_row = {
        "end_date": "20251231",
        "revenue": 1e9,
        "net_income": 1e8,
        "revenue_yoy": 0.1,
        "net_income_yoy": 0.2,
        "roe": 0.15,
        "debt_ratio": 0.4,
    }
    sync_row = {
        "last_sync_at": "t1",
        "latest_end_date": "20251231",
        "periods_count": 4,
        "sync_status": "ok",
        "error_message": "",
    }
    disc_rows = [
        {"end_date": "20251231", "pre_date": "20260110", "ann_date": "", "actual_date": ""},
        {"end_date": "20250930", "pre_date": "", "ann_date": "20251020", "actual_date": ""},
        {"end_date": "20250630", "pre_date": "", "ann_date": "", "actual_date": "20250715"},
        {"end_date": "20250331", "pre_date": "", "ann_date": "", "actual_date": ""},  # 第 4 条应被 LIMIT 截断，由 SQL 保证；mock 只返回 3
    ]
    snap = MagicMock()
    snap.mappings.return_value.first.return_value = snap_row
    meta = MagicMock()
    meta.mappings.return_value.first.return_value = sync_row
    disc = MagicMock()
    disc.mappings.return_value.all.return_value = disc_rows[:3]
    db.execute.side_effect = [snap, meta, disc]
    out = fund.get_fundamentals(db, "600519.SSE")
    assert out["snapshot"]["end_date"] == "20251231"
    assert out["snapshot"]["roe"] == 0.15
    assert out["sync"]["periods_count"] == 4
    assert len(out["disclosures"]) == 3
    assert out["disclosures"][0]["end_date"] == "20251231"
```

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && uv run pytest tests/test_fundamentals.py -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现服务**

```python
"""自选基本面只读：财报 snapshot + 披露日历。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.bar_download import to_ts_code
from app.services.symbols import parse_flexible_symbol, to_vt_symbol

DISCLOSURE_LIMIT = 3


def get_fundamentals(db: Session, vt_symbol: str) -> dict[str, Any]:
    raw = (vt_symbol or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="代码为空")
    try:
        symbol, exchange = parse_flexible_symbol(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    vt = to_vt_symbol(symbol, exchange)
    ts = to_ts_code(symbol, exchange)

    snap = db.execute(
        text(
            """
            SELECT end_date, revenue, net_income, revenue_yoy, net_income_yoy, roe, debt_ratio
            FROM app.financial_snapshots
            WHERE ts_code = :ts
            ORDER BY end_date DESC
            LIMIT 1
            """
        ),
        {"ts": ts},
    ).mappings().first()

    sync = db.execute(
        text(
            """
            SELECT last_sync_at, latest_end_date, periods_count, sync_status, error_message
            FROM app.financial_sync_meta
            WHERE ts_code = :ts
            """
        ),
        {"ts": ts},
    ).mappings().first()

    discs = db.execute(
        text(
            """
            SELECT end_date, pre_date, ann_date, actual_date
            FROM app.disclosure_calendar
            WHERE ts_code = :ts
            ORDER BY end_date DESC
            LIMIT :lim
            """
        ),
        {"ts": ts, "lim": DISCLOSURE_LIMIT},
    ).mappings().all()

    return {
        "vt_symbol": vt,
        "ts_code": ts,
        "snapshot": dict(snap) if snap else None,
        "sync": dict(sync) if sync else None,
        "disclosures": [dict(r) for r in discs],
    }
```

- [ ] **Step 4: 跑测通过**

Run: `cd backend && uv run pytest tests/test_fundamentals.py -v`  
Expected: PASS（按 mock 微调 `.mappings()` 链式调用若失败）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/fundamentals.py backend/tests/test_fundamentals.py
git commit -m "$(cat <<'EOF'
feat(fundamentals): 只读查询财报 snapshot 与披露日历

供自选详情基本面卡片使用。
EOF
)"
```

---

### Task 2: Schema + HTTP 路由

**Files:**
- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/app/api/v1/watchlist.py`
- Modify: `backend/tests/test_fundamentals.py`

**Interfaces:**
- `GET /api/v1/watchlist/items/{vt_symbol}/fundamentals` → `FundamentalsOut`

- [ ] **Step 1: API 测**

```python
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User


def _client() -> TestClient:
    app = create_app()
    now = datetime.now(UTC)
    u = User(
        id=str(uuid4()),
        username="demo",
        display_name="Demo",
        password_hash=hash_password("x"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    def override_db():
        yield MagicMock()

    def override_user():
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def test_api_fundamentals_ok() -> None:
    client = _client()
    fake = {
        "vt_symbol": "600519.SSE",
        "ts_code": "600519.SH",
        "snapshot": None,
        "sync": None,
        "disclosures": [],
    }
    with patch("app.api.v1.watchlist.fundamentals_svc.get_fundamentals", return_value=fake) as g:
        r = client.get("/api/v1/watchlist/items/600519.SSE/fundamentals")
    assert r.status_code == 200
    assert r.json()["ts_code"] == "600519.SH"
    g.assert_called_once()


def test_api_fundamentals_bad_symbol() -> None:
    client = _client()
    with patch(
        "app.api.v1.watchlist.fundamentals_svc.get_fundamentals",
        side_effect=HTTPException(status_code=400, detail="代码为空"),
    ):
        r = client.get("/api/v1/watchlist/items/%20/fundamentals")
    # 空或空格：服务或路由层 400；若路由先 decode 为空则同样 400
    assert r.status_code == 400
```

（第二个测若路径难测可改为直接调 service，保留一个 API 200 测即可。）

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && uv run pytest tests/test_fundamentals.py::test_api_fundamentals_ok -v`  
Expected: FAIL（404）

- [ ] **Step 3: schema + 路由**

在 `schemas/watchlist.py` 追加：

```python
class FinancialSnapshotOut(BaseModel):
    end_date: str
    revenue: float | None = None
    net_income: float | None = None
    revenue_yoy: float | None = None
    net_income_yoy: float | None = None
    roe: float | None = None
    debt_ratio: float | None = None


class FinancialSyncOut(BaseModel):
    last_sync_at: str
    latest_end_date: str = ""
    periods_count: int = 0
    sync_status: str = "ok"
    error_message: str = ""


class DisclosureOut(BaseModel):
    end_date: str
    pre_date: str = ""
    ann_date: str = ""
    actual_date: str = ""


class FundamentalsOut(BaseModel):
    vt_symbol: str
    ts_code: str
    snapshot: FinancialSnapshotOut | None = None
    sync: FinancialSyncOut | None = None
    disclosures: list[DisclosureOut] = Field(default_factory=list)
```

`watchlist.py`：

```python
from app.schemas.watchlist import FundamentalsOut  # 加入 import
from app.services import fundamentals as fundamentals_svc

@router.get("/watchlist/items/{vt_symbol}/fundamentals", response_model=FundamentalsOut)
def get_item_fundamentals(
    vt_symbol: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FundamentalsOut:
    _ = user
    return FundamentalsOut(**fundamentals_svc.get_fundamentals(db, vt_symbol))
```

放在较前的静态路径旁（避免被其它动态路由误伤；当前无 `/watchlist/{id}` 冲突，放 `get_bars` 附近即可）。

- [ ] **Step 4: 跑测通过**

Run: `cd backend && uv run pytest tests/test_fundamentals.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/watchlist.py backend/app/api/v1/watchlist.py backend/tests/test_fundamentals.py
git commit -m "$(cat <<'EOF'
feat(api): 暴露自选标的基本面读接口

GET watchlist/items/{vt}/fundamentals。
EOF
)"
```

---

### Task 3: Watchlist 基本面卡片

**Files:**
- Modify: `frontend/src/api/watchlist.ts`
- Modify: `frontend/src/views/WatchlistView.vue`

- [ ] **Step 1: API 客户端**

```typescript
export type Fundamentals = {
  vt_symbol: string
  ts_code: string
  snapshot: {
    end_date: string
    revenue: number | null
    net_income: number | null
    revenue_yoy: number | null
    net_income_yoy: number | null
    roe: number | null
    debt_ratio: number | null
  } | null
  sync: {
    last_sync_at: string
    latest_end_date: string
    periods_count: number
    sync_status: string
    error_message: string
  } | null
  disclosures: {
    end_date: string
    pre_date: string
    ann_date: string
    actual_date: string
  }[]
}

// watchlistApi 内：
  fundamentals: (vtSymbol: string) =>
    api<Fundamentals>(
      `/api/v1/watchlist/items/${encodeURIComponent(vtSymbol)}/fundamentals`,
    ),
```

- [ ] **Step 2: 状态与加载**

在 `WatchlistView.vue` script（`bars` 旁）增加：

```typescript
const fundOpen = ref(true)
const fundLoading = ref(false)
const fundError = ref('')
const fund = ref<Fundamentals | null>(null)

function formatYmd(raw: string | null | undefined): string {
  const s = (raw || '').trim()
  if (!s) return '—'
  if (/^\d{8}$/.test(s)) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  return s
}

function formatMoney(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(2)} 亿`
  if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(2)} 万`
  return n.toFixed(2)
}

function formatRatioPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(1)}%`
}

async function loadFundamentals() {
  fundError.value = ''
  fund.value = null
  if (!selected.value) {
    fundLoading.value = false
    return
  }
  fundLoading.value = true
  try {
    fund.value = await watchlistApi.fundamentals(selected.value.vt_symbol)
  } catch (e) {
    fundError.value = e instanceof Error ? e.message : '基本面加载失败'
  } finally {
    fundLoading.value = false
  }
}
```

在现有 `watch(selected, () => { void loadBars() ...})` 中同时 `void loadFundamentals()`。

确保 `import type { Fundamentals }` 或从 watchlist 导出类型。

- [ ] **Step 3: 模板（日 K `</template>` 之后、右侧 `</section>` 之前）**

```vue
          <div v-if="selected" class="fund-card">
            <div class="fund-head">
              <h3>基本面</h3>
              <button type="button" class="ghost" @click="fundOpen = !fundOpen">
                {{ fundOpen ? '收起' : '展开' }}
              </button>
            </div>
            <template v-if="fundOpen">
              <p v-if="fundLoading" class="muted">加载基本面…</p>
              <p v-else-if="fundError" class="err">{{ fundError }}</p>
              <template v-else-if="fund">
                <div class="fund-block">
                  <h4>财报</h4>
                  <template v-if="fund.snapshot">
                    <p class="muted">
                      期末 {{ formatYmd(fund.snapshot.end_date) }}
                      <span v-if="fund.sync?.last_sync_at"> · 同步 {{ fund.sync.last_sync_at }}</span>
                    </p>
                    <dl class="fund-grid">
                      <div><dt>营收</dt><dd class="mono">{{ formatMoney(fund.snapshot.revenue) }}</dd></div>
                      <div><dt>净利</dt><dd class="mono">{{ formatMoney(fund.snapshot.net_income) }}</dd></div>
                      <div><dt>营收同比</dt><dd>{{ formatRatioPct(fund.snapshot.revenue_yoy) }}</dd></div>
                      <div><dt>净利同比</dt><dd>{{ formatRatioPct(fund.snapshot.net_income_yoy) }}</dd></div>
                      <div><dt>ROE</dt><dd>{{ formatRatioPct(fund.snapshot.roe) }}</dd></div>
                      <div><dt>资产负债率</dt><dd>{{ formatRatioPct(fund.snapshot.debt_ratio) }}</dd></div>
                    </dl>
                  </template>
                  <p v-else class="muted">
                    暂无财报
                    <RouterLink to="/ops" class="draft-link">去 Ops 同步自选财报</RouterLink>
                  </p>
                </div>
                <div class="fund-block">
                  <h4>披露</h4>
                  <template v-if="fund.disclosures.length">
                    <table class="fund-disc">
                      <thead>
                        <tr>
                          <th>报告期</th>
                          <th>预告</th>
                          <th>公告</th>
                          <th>实际</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="d in fund.disclosures" :key="d.end_date">
                          <td class="mono">{{ formatYmd(d.end_date) }}</td>
                          <td class="mono">{{ formatYmd(d.pre_date) }}</td>
                          <td class="mono">{{ formatYmd(d.ann_date) }}</td>
                          <td class="mono">{{ formatYmd(d.actual_date) }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </template>
                  <p v-else class="muted">
                    暂无披露日历
                    <RouterLink to="/ops" class="draft-link">去 Ops 同步披露计划</RouterLink>
                  </p>
                </div>
              </template>
            </template>
          </div>
```

补 CSS（对齐现有 card：`--bg-elevated` / `--border` / grid gap）。已有 `RouterLink` 与 `.draft-link` 则复用。

- [ ] **Step 4: build**

Run: `cd frontend && npm run build`  
Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/watchlist.ts frontend/src/views/WatchlistView.vue
git commit -m "$(cat <<'EOF'
feat(watchlist): 详情展示财报要点与披露日历

空态引导 Ops 同步自选财报与披露计划。
EOF
)"
```

---

### Task 4: 文档与总验收

**Files:**
- Modify: `docs/product-roadmap.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: 路线图**

在 #42 后追加：

```markdown
43. ~~自选详情基本面（财报+披露）~~（已完成 → [spec](./superpowers/specs/2026-08-13-watchlist-fundamentals-ux-design.md)）
```

- [ ] **Step 2: smoke**

在自选 · 行情节（`/watchlist` 相关条后）加：

```markdown
- [ ] `/watchlist` 选中标的右侧「基本面」：有数据可见财报要点与披露行；无财报/无披露见「去 Ops」链；切换标的会重新加载
```

- [ ] **Step 3: check.sh**

Run: `./scripts/check.sh`  
Expected: 绿

- [ ] **Step 4: Commit**

```bash
git add docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 记录自选详情基本面财报与披露完成

更新路线图 #43 与 smoke 验收项。
EOF
)"
```

---

## Spec coverage（自检）

| Spec | Task |
|------|------|
| get_fundamentals 查询语义 | 1 |
| HTTP + schema | 2 |
| 详情卡片 + 格式化 + Ops 空态 | 3 |
| roadmap + smoke | 4 |
| 不改 Ops/列表/board | 遵守 |

无 TBD。
