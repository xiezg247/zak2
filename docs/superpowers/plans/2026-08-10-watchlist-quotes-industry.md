# 自选/看盘 quotes enrich 读 app.stock_industry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 自选 `_enrich` 与 `GET /quotes` 在 Redis 行业为空时用 `app.stock_industry` 补全，Watchlist 表展示行业列。

**Architecture:** 复用 `enrich_rows_from_db`；`_enrich` / `get_quotes` 将行情（或空行）建成 `QuoteRow` 后补全，写入 schema 的 `industry`；前端列表加列。Redis 非空不覆盖；`with_quotes=False` 时 `industry=""`。

**Tech Stack:** FastAPI、SQLAlchemy Session、QuoteRow、Vue 3、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-watchlist-quotes-industry-design.md`

## Global Constraints

- 只改 zak2；不改 zak
- 不写 Redis；不改 sync；不含策略板；不新增按 symbol 增量 load
- Commit 仅用户明确要求时（默认跳过 Step Commit）
- 不打真网

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/schemas/watchlist.py` | `WatchlistItemOut` / `QuoteOut` 加 `industry` |
| `backend/app/api/v1/watchlist.py` | `_enrich(db=...)`；`get_quotes` 注入 db + enrich |
| `backend/tests/test_watchlist_industry_enrich.py` | **新建** `_enrich` / `/quotes` 单测 |
| `frontend/src/api/watchlist.ts` | `WatchlistItem.industry` |
| `frontend/src/views/WatchlistView.vue` | 行业列 + 详情头 |
| `docs/gap-vs-desktop.md` / `docs/smoke-checklist.md` | 缺口与 smoke |

---

### Task 1: Schema + `_enrich` 行业补全

**Files:**
- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/app/api/v1/watchlist.py`
- Create: `backend/tests/test_watchlist_industry_enrich.py`

**Interfaces:**
- `WatchlistItemOut.industry: str = ""`
- `QuoteOut.industry: str = ""`（本 task 先加 schema；`get_quotes` 接线在 Task 2）
- `_enrich(items, *, with_quotes: bool, db: Session | None = None) -> list[WatchlistItemOut]`
  - `with_quotes=False` → 所有 `industry=""`（不查库）
  - `with_quotes=True` → 拉 Redis（若可用）；对每个 item 建 `QuoteRow(symbol=tf, name=..., industry=getattr(q,"industry","") or "")`；`enrich_rows_from_db(db, rows)`；出参用补全后的 `industry`
  - **无 Redis 行情行时仍可补行业**（用空 `QuoteRow` + map）
- 所有调用 `_enrich` 处传入 `db`（`get_watchlist` 等已有 `db`）

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_watchlist_industry_enrich.py
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.v1 import watchlist as wl
from app.services.quotes import QuoteRow


def _item(symbol: str = "600519", exchange: str = "SSE", name: str = "茅台", sort: int = 0):
    return SimpleNamespace(symbol=symbol, exchange=exchange, name=name, sort_order=sort)


def test_enrich_fills_empty_industry_from_db() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.get_quotes.return_value = [
        QuoteRow(symbol="SHSE.600519", name="茅台", last_price=100.0, industry=""),
    ]
    db = MagicMock()
    with (
        patch.object(wl, "get_quote_store", return_value=store),
        patch.object(wl, "enrich_rows_from_db", side_effect=lambda _db, rows: (
            setattr(rows[0], "industry", "白酒") or 1
        )) as enrich_mock,
    ):
        out = wl._enrich([_item()], with_quotes=True, db=db)
    assert out[0].industry == "白酒"
    enrich_mock.assert_called_once()
    assert enrich_mock.call_args.args[0] is db


def test_enrich_keeps_redis_industry() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.get_quotes.return_value = [
        QuoteRow(symbol="SHSE.600519", name="茅台", industry="已有行业"),
    ]

    def fake_enrich(_db, rows):
        assert rows[0].industry == "已有行业"
        return 0

    with (
        patch.object(wl, "get_quote_store", return_value=store),
        patch.object(wl, "enrich_rows_from_db", side_effect=fake_enrich),
    ):
        out = wl._enrich([_item()], with_quotes=True, db=MagicMock())
    assert out[0].industry == "已有行业"


def test_enrich_without_quotes_skips_industry() -> None:
    with patch.object(wl, "enrich_rows_from_db") as enrich_mock:
        out = wl._enrich([_item()], with_quotes=False, db=MagicMock())
    enrich_mock.assert_not_called()
    assert out[0].industry == ""
    assert out[0].last_price is None


def test_enrich_no_redis_still_looks_up_db() -> None:
    store = MagicMock()
    store.available.return_value = False

    def fill(_db, rows):
        assert len(rows) == 1
        assert rows[0].symbol == "SHSE.600519"
        rows[0].industry = "白酒"
        return 1

    with (
        patch.object(wl, "get_quote_store", return_value=store),
        patch.object(wl, "enrich_rows_from_db", side_effect=fill),
    ):
        out = wl._enrich([_item()], with_quotes=True, db=MagicMock())
    assert out[0].industry == "白酒"
```

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && python -m pytest tests/test_watchlist_industry_enrich.py -v`  
Expected: FAIL（`industry` 字段不存在或 `_enrich` 无 `db` / 未调 enrich）

- [ ] **Step 3: Schema**

`WatchlistItemOut` 与 `QuoteOut` 增加：

```python
industry: str = ""
```

（`QuoteOut` 放在行情字段末尾，默认 `""`。）

- [ ] **Step 4: 实现 `_enrich`**

```python
from app.services.quotes import QuoteRow, get_quote_store
from app.services.stock_industry import enrich_rows_from_db

def _enrich(items: list, *, with_quotes: bool, db: Session | None = None) -> list[WatchlistItemOut]:
    quote_map: dict[str, QuoteRow] = {}
    if with_quotes and items:
        store = get_quote_store()
        if store.available():
            tfs = [to_tf_symbol(i.symbol, i.exchange) for i in items]
            for q in store.get_quotes(tfs):
                quote_map[q.symbol] = q

    rows: list[QuoteRow] = []
    if with_quotes and items:
        for item in items:
            tf = to_tf_symbol(item.symbol, item.exchange)
            q = quote_map.get(tf)
            rows.append(
                QuoteRow(
                    symbol=tf,
                    name=(q.name if q and q.name else item.name) or "",
                    last_price=q.last_price if q else 0.0,
                    change_pct=q.change_pct if q else 0.0,
                    turnover_rate=q.turnover_rate if q else 0.0,
                    volume=q.volume if q else 0.0,
                    amount=q.amount if q else 0.0,
                    volume_ratio=q.volume_ratio if q else 0.0,
                    industry=(q.industry if q else "") or "",
                )
            )
        enrich_rows_from_db(db, rows)

    industry_by_tf = {r.symbol: r.industry for r in rows}
    out: list[WatchlistItemOut] = []
    for item in items:
        tf = to_tf_symbol(item.symbol, item.exchange)
        q = quote_map.get(tf)
        name = item.name
        if q is not None and q.name:
            name = q.name
        out.append(
            WatchlistItemOut(
                symbol=item.symbol,
                exchange=item.exchange,
                name=name,
                sort_order=item.sort_order,
                vt_symbol=to_vt_symbol(item.symbol, item.exchange),
                tf_symbol=tf,
                last_price=q.last_price if q else None,
                change_pct=q.change_pct if q else None,
                turnover_rate=q.turnover_rate if q else None,
                volume=q.volume if q else None,
                amount=q.amount if q else None,
                volume_ratio=q.volume_ratio if q else None,
                industry=industry_by_tf.get(tf, "") if with_quotes else "",
            )
        )
    return out
```

更新调用点传入 `db`，例如：

```python
return _enrich(items, with_quotes=enrich, db=db)
# POST add 等：_enrich([row], with_quotes=True, db=db)
# reorder：_enrich(rows, with_quotes=False, db=db)  # industry 仍为空
```

- [ ] **Step 5: 跑测通过**

Run: `cd backend && python -m pytest tests/test_watchlist_industry_enrich.py -v`  
Expected: PASS

- [ ] **Step 6: Commit（仅用户要求时）**

```bash
git add backend/app/schemas/watchlist.py backend/app/api/v1/watchlist.py backend/tests/test_watchlist_industry_enrich.py
git commit -m "$(cat <<'EOF'
feat(watchlist): 自选 enrich 用 stock_industry 补全空行业

EOF
)"
```

---

### Task 2: `GET /quotes` 接线

**Files:**
- Modify: `backend/app/api/v1/watchlist.py`（`get_quotes`）
- Modify: `backend/tests/test_watchlist_industry_enrich.py`

**Interfaces:**
- `get_quotes(..., db: Session = Depends(get_db))`
- 有 Redis 行情后：对 `meta` 顺序建 `QuoteRow` → `enrich_rows_from_db(db, rows)` → `QuoteOut.industry`

- [ ] **Step 1: 追加失败单测**

```python
# 追加到 test_watchlist_industry_enrich.py
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User


def _make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=str(uuid4()),
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _api_client(*, db: MagicMock | None = None) -> TestClient:
    app = create_app()
    session = db if db is not None else MagicMock()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    return TestClient(app)


def test_quotes_endpoint_enriches_industry() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.get_quotes.return_value = [
        QuoteRow(symbol="SHSE.600519", name="茅台", last_price=100.0, industry=""),
    ]

    def fill(_db, rows):
        rows[0].industry = "白酒"
        return 1

    with (
        patch.object(wl, "get_quote_store", return_value=store),
        patch.object(wl, "enrich_rows_from_db", side_effect=fill),
    ):
        client = _api_client()
        resp = client.get("/api/v1/quotes", params={"symbols": "600519.SSE"})
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["industry"] == "白酒"
```

（确认路由前缀：若 quotes 挂在同一 router 且 prefix 无 `/watchlist`，路径为 `/api/v1/quotes`；以 `app.api` 注册为准，测不通时改路径。）

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && python -m pytest tests/test_watchlist_industry_enrich.py::test_quotes_endpoint_enriches_industry -v`  
Expected: FAIL（响应无 industry 或未 enrich）

- [ ] **Step 3: 实现 `get_quotes`**

在现有循环前/中：

```python
@router.get("/quotes", response_model=list[QuoteOut])
def get_quotes(
    symbols: str = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuoteOut]:
    _ = user
    store = get_quote_store()
    if not store.available():
        raise HTTPException(status_code=503, detail="Redis 不可用")
    # ... 解析 tf_list / meta 不变 ...
    quotes = {q.symbol: q for q in store.get_quotes(tf_list)}
    rows: list[QuoteRow] = []
    for symbol, exchange, tf in meta:
        q = quotes.get(tf)
        rows.append(
            QuoteRow(
                symbol=tf,
                name=q.name if q else "",
                last_price=q.last_price if q else 0.0,
                change_pct=q.change_pct if q else 0.0,
                turnover_rate=q.turnover_rate if q else 0.0,
                volume=q.volume if q else 0.0,
                amount=q.amount if q else 0.0,
                amplitude=q.amplitude if q else 0.0,
                volume_ratio=q.volume_ratio if q else 0.0,
                industry=(q.industry if q else "") or "",
            )
        )
    enrich_rows_from_db(db, rows)
    out: list[QuoteOut] = []
    for (symbol, exchange, tf), row in zip(meta, rows, strict=True):
        out.append(
            QuoteOut(
                symbol=symbol,
                exchange=exchange,
                vt_symbol=to_vt_symbol(symbol, exchange),
                tf_symbol=tf,
                name=row.name,
                last_price=row.last_price,
                change_pct=row.change_pct,
                turnover_rate=row.turnover_rate,
                volume=row.volume,
                amount=row.amount,
                amplitude=row.amplitude,
                volume_ratio=row.volume_ratio,
                industry=row.industry or "",
            )
        )
    return out
```

- [ ] **Step 4: 跑测通过**

Run: `cd backend && python -m pytest tests/test_watchlist_industry_enrich.py -v`  
Expected: PASS

- [ ] **Step 5: Commit（仅用户要求时）**

```bash
git add backend/app/api/v1/watchlist.py backend/tests/test_watchlist_industry_enrich.py
git commit -m "$(cat <<'EOF'
feat(watchlist): GET /quotes 补全空行业

EOF
)"
```

---

### Task 3: 前端行业列 + 文档

**Files:**
- Modify: `frontend/src/api/watchlist.ts`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

**Interfaces:**
- `WatchlistItem.industry?: string`
- 表头「名称」后「行业」；空 `—`；`colspan` 同步 +1
- 详情头：`selected.industry` 非空时显示

- [ ] **Step 1: 类型**

```typescript
export type WatchlistItem = {
  // ...existing...
  industry?: string
}
```

- [ ] **Step 2: WatchlistView 列表与详情**

表头：

```html
<th>代码</th>
<th>名称</th>
<th>行业</th>
<th>现价</th>
<th>涨幅%</th>
<th></th>
```

单元格：

```html
<td>{{ item.industry?.trim() ? item.industry : '—' }}</td>
```

空表：`colspan="6"`。

详情头（`chart-head` 内名称旁）：

```html
<span v-if="selected.industry?.trim()" class="muted">{{ selected.industry }}</span>
```

- [ ] **Step 3: 文档**

`docs/gap-vs-desktop.md`：
- 「建议下一刀」第 1 条改为已完成或删除，并在自选相关行注明 quotes enrich 已读 `app.stock_industry`
- 示例：自选 CRUD 行备注「Redis 空行业时 list/quotes 读 stock_industry」

`docs/smoke-checklist.md` §3 自选 · 行情：
- 增加：`- [ ] Ops 已同步行业映射后，自选列表「行业」列在 Redis 缺 industry 时仍可见行业名`

- [ ] **Step 4: 构建与全量相关测**

Run:

```bash
cd backend && python -m pytest tests/test_watchlist_industry_enrich.py tests/test_stock_industry.py -v
cd ../frontend && npm run build
```

Expected: pytest PASS；`npm run build` 成功

- [ ] **Step 5: Commit（仅用户要求时）**

```bash
git add frontend/src/api/watchlist.ts frontend/src/views/WatchlistView.vue docs/gap-vs-desktop.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
feat(watchlist): 自选列表展示行业列

EOF
)"
```

---

## Spec coverage（自检）

| Spec 要求 | Task |
|-----------|------|
| WatchlistItemOut / QuoteOut.industry | 1 |
| `_enrich` + enrich_rows_from_db；非空不覆盖；enrich=false 为空 | 1 |
| 无 Redis 行情仍可查库 | 1 |
| GET /quotes + db | 2 |
| 前端行业列 | 3 |
| gap / smoke | 3 |
| 策略板 / 写 Redis / 增量 load | 非目标，未做 |

## Placeholder scan

无 TBD / 「类似 Task N」；测试与实现代码已内嵌。
