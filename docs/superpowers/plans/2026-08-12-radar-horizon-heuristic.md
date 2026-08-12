# 雷达展望启发式写读闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `scan_horizon_outlook` 用共振启发式写入 `radar_horizon_cache`；`GET /radar/horizon` + 雷达页展示。

**Architecture:** Job 调 `list_radar_cards` + `compute_resonance`（默认权重）→ upsert horizon cache；读服务 + API；`RadarView` 拉展示。不做 predict。

**Tech Stack:** FastAPI、SQLAlchemy、Vue 3、pytest

**Spec:** `docs/superpowers/specs/2026-08-12-radar-horizon-heuristic-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*；不写 `radar_predict_cache`
- Job **不再**恒 skipped；空共振仍 `success=True` 写空 rows
- 不 `needs_user_id`；用默认 `CARD_WEIGHTS`
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/ops_scan_horizon_outlook.py` | 真写 |
| `backend/app/services/radar_horizon.py` | 读 cache |
| `backend/app/schemas/market.py` | Out |
| `backend/app/api/v1/market.py` | GET |
| `backend/tests/test_ops_scan_horizon_outlook.py` | job 测 |
| `backend/tests/test_radar_horizon.py` | 读测 |
| `frontend/src/api/market.ts` / `RadarView.vue` | 前端 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: 做实 `scan_horizon_outlook` 写 cache

**Files:**
- Modify: `backend/app/services/ops_scan_horizon_outlook.py`
- Modify: `backend/tests/test_ops_scan_horizon_outlook.py`

**Interfaces:**
- Produces: `scan_horizon_outlook(db) -> {success, skipped: False, message, written, strategy_key}`
- Consumes: `list_radar_cards`, `compute_resonance`, `save_job_run_meta`

- [ ] **Step 1: 重写测试（替换 skipped 断言）**

```python
# backend/tests/test_ops_scan_horizon_outlook.py
from unittest.mock import MagicMock, patch

from app.schemas.market import RadarCardOut, RadarResonanceEntry, RadarResonanceOut
from app.services import ops_scan_horizon_outlook as m


def test_horizon_writes_rows() -> None:
    db = MagicMock()
    cards = [
        RadarCardOut(
            card_id="c1", title="T", source="synthesized", rows=[{"vt_symbol": "600519.SSE", "name": "茅台"}]
        )
    ]
    resonance = RadarResonanceOut(
        min_cards=2,
        top_n=30,
        total=1,
        entries=[
            RadarResonanceEntry(
                vt_symbol="600519.SSE",
                name="茅台",
                card_count=2,
                card_titles=["T"],
                resonance_score=1.5,
                change_pct=1.0,
                last_price=100.0,
            )
        ],
    )
    with (
        patch.object(m, "list_radar_cards", return_value=cards),
        patch.object(m, "compute_resonance", return_value=resonance),
        patch.object(m, "save_job_run_meta") as save,
        patch.object(m, "_upsert_horizon") as upsert,
    ):
        out = m.scan_horizon_outlook(db)
    assert out["success"] is True
    assert out["skipped"] is False
    assert out["written"] == 1
    assert out["strategy_key"] == "resonance_heuristic"
    upsert.assert_called_once()
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_horizon_empty_still_success() -> None:
    db = MagicMock()
    with (
        patch.object(m, "list_radar_cards", return_value=[]),
        patch.object(
            m,
            "compute_resonance",
            return_value=RadarResonanceOut(min_cards=2, top_n=30, total=0, entries=[]),
        ),
        patch.object(m, "save_job_run_meta") as save,
        patch.object(m, "_upsert_horizon") as upsert,
    ):
        out = m.scan_horizon_outlook(db)
    assert out["success"] is True
    assert out["skipped"] is False
    assert out["written"] == 0
    upsert.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True
```

（若 `RadarCardOut` 构造字段不同，按实际 schema 微调。）

- [ ] **Step 2: 跑测确认失败（旧 skipped 行为）**

```bash
cd backend && uv run pytest tests/test_ops_scan_horizon_outlook.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现**

```python
"""雷达展望：共振启发式写入 cache.radar_horizon_cache。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta
from app.services.radar import list_radar_cards
from app.services.radar_resonance import compute_resonance

JOB_ID = "scan_horizon_outlook"
STRATEGY_KEY = "resonance_heuristic"
VARIANT = "default"
TOP_N = 30
MIN_CARDS = 2


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _upsert_horizon(
    db: Session,
    *,
    rows: list[dict[str, Any]],
    scanned_total: int,
    refined_total: int,
    computed_at: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO cache.radar_horizon_cache (
                variant, rows_json, scanned_total, excluded_count,
                prefilter_total, refined_total, kline_missing, strategy_key, computed_at
            ) VALUES (
                :variant, :rows_json, :scanned_total, 0,
                :prefilter_total, :refined_total, 0, :strategy_key, :computed_at
            )
            ON CONFLICT (variant) DO UPDATE SET
                rows_json = EXCLUDED.rows_json,
                scanned_total = EXCLUDED.scanned_total,
                excluded_count = EXCLUDED.excluded_count,
                prefilter_total = EXCLUDED.prefilter_total,
                refined_total = EXCLUDED.refined_total,
                kline_missing = EXCLUDED.kline_missing,
                strategy_key = EXCLUDED.strategy_key,
                computed_at = EXCLUDED.computed_at
            """
        ),
        {
            "variant": VARIANT,
            "rows_json": json.dumps(rows, ensure_ascii=False),
            "scanned_total": scanned_total,
            "prefilter_total": scanned_total,
            "refined_total": refined_total,
            "strategy_key": STRATEGY_KEY,
            "computed_at": computed_at,
        },
    )
    db.commit()


def scan_horizon_outlook(db: Session) -> dict[str, Any]:
    cards = list_radar_cards(db)
    resonance = compute_resonance(cards, min_cards=MIN_CARDS, top_n=TOP_N)
    rows = [
        {
            "vt_symbol": e.vt_symbol,
            "name": e.name,
            "resonance_score": e.resonance_score,
            "card_count": e.card_count,
            "card_titles": e.card_titles,
            "change_pct": e.change_pct,
            "last_price": e.last_price,
            "seal_time_label": e.seal_time_label or "",
        }
        for e in resonance.entries
    ]
    # scanned：卡片内出现过的 vt 近似；简化可用 sum(len(c.rows) for c in cards)
    scanned = sum(len(c.rows or []) for c in cards)
    computed_at = _now_iso()
    _upsert_horizon(
        db,
        rows=rows,
        scanned_total=scanned,
        refined_total=len(rows),
        computed_at=computed_at,
    )
    msg = f"启发式展望已写入 {len(rows)} 条（resonance_heuristic）"
    if not rows:
        msg = "启发式展望已写入 0 条（无达标共振标的）"
    save_job_run_meta(db, JOB_ID, last_message=msg, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": msg,
        "written": len(rows),
        "strategy_key": STRATEGY_KEY,
    }
```

（`db.commit()` 是否与其它 ops 一致：对照 `ops_warm_radar`；若 runner 外层 commit 则去掉内层。）

- [ ] **Step 4: 跑测**

```bash
cd backend && uv run pytest tests/test_ops_scan_horizon_outlook.py -q
```

Expected: pass

- [ ] **Step 5: 更新 catalog 描述（若仍写「占位 skipped」）**

在 `ops_catalog.py` 中 `scan_horizon_outlook` 的描述改为「共振启发式 → radar_horizon_cache」。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ops_scan_horizon_outlook.py backend/tests/test_ops_scan_horizon_outlook.py backend/app/services/ops_catalog.py
git commit -m "$(cat <<'EOF'
feat(ops): 做实 scan_horizon_outlook 启发式写 cache

基于雷达共振写入 radar_horizon_cache，不再恒 skipped。
EOF
)"
```

---

### Task 2: `GET /radar/horizon` 读路径

**Files:**
- Create: `backend/app/services/radar_horizon.py`
- Modify: `backend/app/schemas/market.py`
- Modify: `backend/app/api/v1/market.py`
- Create: `backend/tests/test_radar_horizon.py`

- [ ] **Step 1: schema**

```python
class RadarHorizonRow(BaseModel):
    vt_symbol: str
    name: str = ""
    resonance_score: float = 0
    card_count: int = 0
    card_titles: list[str] = Field(default_factory=list)
    change_pct: float | None = None
    last_price: float | None = None
    seal_time_label: str = ""


class RadarHorizonOut(BaseModel):
    variant: str = "default"
    strategy_key: str = ""
    computed_at: str | None = None
    scanned_total: int = 0
    refined_total: int = 0
    rows: list[RadarHorizonRow] = Field(default_factory=list)
    empty: bool = True
    label: str = "启发式展望（基于共振）"
```

- [ ] **Step 2: service + 测试**

```python
# radar_horizon.py
def load_horizon(db: Session, *, variant: str = "default") -> RadarHorizonOut:
    # SELECT ... WHERE variant=:v
    # 无行 → empty Out
    # 有行 → parse rows_json
```

测试：mock execute 无行 / 有行。

- [ ] **Step 3: 路由**

```python
@router.get("/radar/horizon", response_model=RadarHorizonOut)
def get_radar_horizon(...):
    return radar_horizon_svc.load_horizon(db)
```

- [ ] **Step 4: pytest**

```bash
cd backend && uv run pytest tests/test_radar_horizon.py tests/test_ops_scan_horizon_outlook.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/radar_horizon.py backend/app/schemas/market.py backend/app/api/v1/market.py backend/tests/test_radar_horizon.py
git commit -m "$(cat <<'EOF'
feat(radar): 新增 GET /radar/horizon 读展望 cache

返回启发式展望行或空结果。
EOF
)"
```

---

### Task 3: 前端 RadarView 展示

**Files:**
- Modify: `frontend/src/api/market.ts`
- Modify: `frontend/src/views/RadarView.vue`

- [ ] **Step 1: API 客户端**

```typescript
export type RadarHorizon = {
  variant: string
  strategy_key: string
  computed_at: string | null
  scanned_total: number
  refined_total: number
  rows: Array<{
    vt_symbol: string
    name: string
    resonance_score: number
    card_count: number
    card_titles: string[]
    change_pct: number | null
    last_price: number | null
    seal_time_label?: string
  }>
  empty: boolean
  label: string
}

// marketApi.radarHorizon: () => api<RadarHorizon>('/api/v1/radar/horizon')
```

- [ ] **Step 2: RadarView**

- `horizon = ref<RadarHorizon | null>(null)`；在 `load` 中一并请求（失败不阻断卡片）  
- 有 `computed_at`：头显示 `label` 或「启发式」；面板内表格/列表展示 rows；显示时间  
- 无数据：文案改为引导 Ops 跑 `scan_horizon_outlook`（去掉「恒 skipped」）  
- 默认仍可折叠

- [ ] **Step 3: build**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/market.ts frontend/src/views/RadarView.vue
git commit -m "$(cat <<'EOF'
feat(radar): 展望区读取启发式 horizon cache

有数据展示列表；无数据引导 Ops 跑 scan_horizon_outlook。
EOF
)"
```

---

### Task 4: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

替换/增补：

```markdown
- [ ] Ops 手动跑 **`scan_horizon_outlook`** 非 skipped（可写入启发式展望）；`/radar` 展望区可读行或空态引导（文案含启发式/共振，无「恒 skipped」）
```

（更新旧「恒 skipped」条。）

- [ ] **Step 2: roadmap**

```markdown
26. ~~雷达展望启发式写读闭环~~（已完成 → [spec](./superpowers/specs/2026-08-12-radar-horizon-heuristic-design.md)）
```

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs: 记录雷达展望启发式写读闭环完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| job 真写 | 1 |
| GET | 2 |
| RadarView | 3 |
| smoke / roadmap | 4 |

无 TBD。predict 明确不做。
