# 雷达展望加深 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 加深 `scan_horizon_outlook`（封板 map + 漏斗 + 合成卡），同 job 写入 `rules_v1` 规则预测，`/radar` 双区展示。

**Architecture:** 单 job 两阶段：Phase A 共振 → `radar_horizon_cache`；Phase B 可解释规则打分 → `radar_predict_cache`；新 GET `/radar/predict` + RadarView 双折叠区。

**Tech Stack:** FastAPI、SQLAlchemy、Redis QuoteStore、Vue 3、pytest

**Spec:** `docs/superpowers/specs/2026-08-14-radar-horizon-deepen-design.md`

## Global Constraints

- 只改 zak2；不改 zak；不做 LLM
- job 用默认 `CARD_WEIGHTS`，不用用户权重
- `model_label = "rules_v1"`；`strategy_key = "resonance_heuristic"`
- A 成功 B 失败 → job `success=true`，message 含 `predict_error=`
- 合成卡无行则整卡省略（不进 `build_synthesized_cards` 列表）
- commit 简体中文；`./scripts/check.sh` 绿

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/radar.py` | 合成 `discovery_limit_break` / `discovery_volume_surge` |
| `backend/app/services/radar_resonance.py` | `resonance_scan_stats`（去重 scanned / excluded） |
| `backend/app/services/radar_predict.py` | 打分、日 K 批量、upsert、load |
| `backend/app/services/ops_scan_horizon_outlook.py` | 两阶段编排 |
| `backend/app/schemas/market.py` | `RadarPredictRow` / `RadarPredictOut` |
| `backend/app/api/v1/market.py` | `GET /radar/predict` |
| `backend/app/services/ops_catalog.py` | job 描述文案 |
| `frontend/src/api/market.ts` | `radarPredict` 类型与 API |
| `frontend/src/views/RadarView.vue` | 双区 UI |
| `docs/product-roadmap.md` / `docs/smoke-checklist.md` | #52 + smoke |
| 测试 | 见各 Task |

---

### Task 1: 合成卡加宽

**Files:**
- Modify: `backend/app/services/radar.py`
- Test: `backend/tests/test_radar_synth_cards.py`（新建）

**Interfaces:**
- `_synth_limit_break(db) -> RadarCardOut | None`：`list_limit_list(db)` 中 `open_times > 0`，按 `open_times` 降序最多 30；无行 → `None`
- `_synth_volume_surge() -> RadarCardOut | None`：`get_quote_store().list_rank("volume_ratio", top_n=80)`，过滤 `score >= 2`，取 Top30；无行 → `None`
- `build_synthesized_cards`：在现有列表后 `append` 非 `None` 结果
- `list_radar_cards` 的 `priority` 增加：`discovery_limit_break: 1`（ladder 旁）、`discovery_volume_surge: 2`（可微调，保持稳定即可）

- [ ] **Step 1: 写失败测试（mock list_limit_list / quote store）**

```python
from unittest.mock import MagicMock, patch
from app.services import radar as radar_svc

def test_synth_limit_break_filters_open_times():
    db = MagicMock()
    with patch("app.services.radar.list_limit_list", return_value={
        "trade_date": "20260814",
        "rows": [
            {"vt_symbol": "600000.SSE", "name": "浦发", "open_times": 2},
            {"vt_symbol": "600519.SSE", "name": "茅台", "open_times": 0},
        ],
    }):
        # 实现后从 build 或私有函数取卡
        cards = radar_svc.build_synthesized_cards(db)
    break_cards = [c for c in cards if c.card_id == "discovery_limit_break"]
    assert len(break_cards) == 1
    assert break_cards[0].rows[0]["vt_symbol"] == "600000.SSE"
    assert all(float(r.get("open_times") or 0) > 0 for r in break_cards[0].rows)

def test_synth_volume_surge_omits_when_empty():
    store = MagicMock()
    store.available.return_value = True
    store.list_rank.return_value = [("SH600519", 1.5)]  # < 2 → 省略整卡
    with patch("app.services.radar.get_quote_store", return_value=store):
        cards = radar_svc.build_synthesized_cards(MagicMock())
    assert not any(c.card_id == "discovery_volume_surge" for c in cards)
```

注意：`list_limit_list` 当前从 `limit_list_store` 导入；实现时在 `radar.py` 内 `from app.services.limit_list_store import list_limit_list`（与 ladder 的 emotion 路径一致即可）。`_synth_change_top` 已用 `get_quote_store`——volume_surge 同模式；行需带 `vt_symbol`（用现有 `_to_vt_symbol` / quotes 工具把 tf 转 vt，对齐 `discovery_change_top` 行字段习惯；共振侧用 `_row_vt_symbol`，确保行里有可解析的 symbol/vt）。

- [ ] **Step 2: 跑测见红**

```bash
cd backend && uv run pytest tests/test_radar_synth_cards.py -q
```

Expected: FAIL（无卡 / import）

- [ ] **Step 3: 实现合成函数并接入 `build_synthesized_cards`**

`_synth_limit_break` 行字段至少：`vt_symbol`, `name`, `open_times`。  
`_synth_volume_surge` 行字段至少：`vt_symbol`（或 tf+可解析字段）, `name`, `volume_ratio` / `change_pct`/`last_price` 若 quote 有则填。

- [ ] **Step 4: 测绿 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(radar): 合成炸板与放量异动卡

拓宽共振候选，有数据才纳入合成列表。
EOF
)"
```

---

### Task 2: 漏斗统计纯函数

**Files:**
- Modify: `backend/app/services/radar_resonance.py`
- Test: `backend/tests/test_radar_resonance_funnel.py`（新建）

**Interfaces:**
- `def resonance_scan_stats(cards: list[RadarCardOut], *, min_cards: int = 2, weights: dict[str, float] | None = None) -> tuple[int, int]:`
  - 复用与 `compute_resonance` 相同的 vt 归并规则（跳过 weight≤0、STAT 等）
  - 返回 `(scanned_total, excluded_count)`：`scanned_total = len(grouped)`；`excluded_count =` 其中 `card_count < min_cards` 的数量
- 不改 `compute_resonance` 的对外行为

- [ ] **Step 1: 表驱动测试**

```python
from app.schemas.market import RadarCardOut
from app.services.radar_resonance import resonance_scan_stats

def test_resonance_scan_stats_excluded():
    cards = [
        RadarCardOut(card_id="leader_pick", title="A", source="s", rows=[{"vt_symbol": "600519.SSE"}]),
        RadarCardOut(card_id="discovery_change_top", title="B", source="s", rows=[{"vt_symbol": "600519.SSE"}, {"vt_symbol": "000001.SZSE"}]),
    ]
    scanned, excluded = resonance_scan_stats(cards, min_cards=2)
    assert scanned == 2
    assert excluded == 1  # 000001 只出现 1 卡
```

- [ ] **Step 2: 实现 → 绿 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(radar): 共振漏斗 scanned/excluded 统计

供展望 job 如实写入 cache 元数据。
EOF
)"
```

---

### Task 3: 规则预测打分 + cache 读写 + API

**Files:**
- Create: `backend/app/services/radar_predict.py`
- Modify: `backend/app/schemas/market.py`
- Modify: `backend/app/api/v1/market.py`
- Test: `backend/tests/test_radar_predict_score.py`、`backend/tests/test_radar_predict_load.py`

**Interfaces:**

```python
MODEL_LABEL = "rules_v1"
VARIANT = "default"

def score_predict_rows(
    horizon_rows: list[dict],
    *,
    has_daily_bars: set[str],  # vt_symbol 集合
    top_n: int = 30,
) -> tuple[list[dict], int]:
    """返回 (sorted_rows, kline_missing_count)。"""

def vt_with_min_daily_bars(db: Session, vt_symbols: list[str], *, min_bars: int = 5) -> set[str]:
    """批量查 dbbardata interval=d，返回满足根数的 vt 集合。"""

def upsert_predict(db, *, rows, scanned_total, refined_total, kline_missing, computed_at) -> None: ...
def load_predict(db, *, variant: str = "default") -> RadarPredictOut: ...
```

Schema:

```python
class RadarPredictRow(BaseModel):
    vt_symbol: str
    name: str = ""
    predict_score: float = 0
    resonance_score: float = 0
    card_count: int = 0
    card_titles: list[str] = Field(default_factory=list)
    change_pct: float | None = None
    last_price: float | None = None
    seal_time_label: str = ""
    reasons: list[str] = Field(default_factory=list)

class RadarPredictOut(BaseModel):
    variant: str = "default"
    model_label: str = ""
    computed_at: str | None = None
    scanned_total: int = 0
    refined_total: int = 0
    kline_missing: int = 0
    rows: list[RadarPredictRow] = Field(default_factory=list)
    empty: bool = True
    label: str = "规则预测（共振+可解释加分）"
```

打分逻辑（钉死，与 spec §3.2 一致）：

```python
score = float(resonance_score)
reasons = [f"共振 {resonance_score}"]
if card_count >= 4:
    score += 1.0; reasons.append("出现≥4卡")
elif card_count >= 3:
    score += 0.5; reasons.append("出现≥3卡")
if change_pct is not None:
    if change_pct >= 7: score += 0.8; reasons.append("涨幅≥7%")
    elif change_pct >= 3: score += 0.4; reasons.append("涨幅≥3%")
    elif change_pct < 0: score -= 0.5; reasons.append("涨幅为负")
if seal_time_label.strip():
    score += 0.6; reasons.append("有封板时刻")
if vt in has_daily_bars:
    score += 0.3; reasons.append("近5日K可用")
else:
    kline_missing += 1
# sort (-predict_score, -resonance_score, vt); [:top_n]
```

API：

```python
@router.get("/radar/predict", response_model=RadarPredictOut)
def get_radar_predict(user=Depends(get_current_user), db=Depends(get_db)) -> RadarPredictOut:
    _ = user
    return load_predict(db)
```

- [ ] **Step 1: `test_radar_predict_score.py` 表驱动（无 DB）**

覆盖：多卡加成、涨幅档、封板、缺 K 计入返回的 `kline_missing`、排序。

- [ ] **Step 2: 实现 `score_predict_rows` → 绿**

- [ ] **Step 3: schema + `load_predict` 空库行为单测（mock execute → None → empty=True）+ upsert SQL 对齐 horizon 风格**

- [ ] **Step 4: 注册路由 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(radar): 规则预测打分与 /radar/predict

写入 radar_predict_cache，提供可解释 reasons。
EOF
)"
```

---

### Task 4: Job 两阶段编排

**Files:**
- Modify: `backend/app/services/ops_scan_horizon_outlook.py`
- Modify: `backend/app/services/ops_catalog.py`（`scan_horizon_outlook` description）
- Test: 扩展 `backend/tests/test_ops_scan_horizon_outlook.py`

**Interfaces:**
- Phase A：`load_first_time_map(db)` → `compute_resonance(..., first_time_map=ft, top_n=30)`；`resonance_scan_stats` → `_upsert_horizon(..., excluded_count=...)`（扩展 upsert 写入 `excluded_count`，不再写死 0）
- Phase B：`has = vt_with_min_daily_bars(db, [r["vt_symbol"] for r in rows])`；`score_predict_rows`；`upsert_predict`；包在 `try/except`：异常则 `predict_error=str(exc)[:200]`，**不** raise
- 返回 dict 增：`predict_written`, `predict_error`（可空）、`horizon_written`；`success` 在 A 完成后为 True
- catalog 文案：`共振启发式 + 规则预测 → horizon/predict cache`

- [ ] **Step 1: 更新既有 mock 测试**（需 patch `load_first_time_map`、`resonance_scan_stats`、`upsert_predict` / `score_predict_rows` / `vt_with_min_daily_bars`）

```python
def test_horizon_predict_phase_failure_still_success():
    # A ok；B score 或 upsert 抛错
    ...
    assert out["success"] is True
    assert "predict_error" in (out.get("message") or "") or out.get("predict_error")
    # horizon upsert 已调用；predict upsert 未调用或失败前未完整写
```

- [ ] **Step 2: 实现两阶段 → 测绿 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(radar): 展望 job 两阶段写入预测缓存

对齐封板 map 与漏斗，预测失败不丢 horizon。
EOF
)"
```

---

### Task 5: UI + 文档收口

**Files:**
- Modify: `frontend/src/api/market.ts`
- Modify: `frontend/src/views/RadarView.vue`
- Modify: `docs/product-roadmap.md`（#52）
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/superpowers/specs/2026-08-14-radar-horizon-deepen-design.md` 状态 → 已批准（已实现）

**UI:**
- `radarPredict()` 并行于 `radarHorizon()`
- 「展望」→「共振展望」；新增「规则预测」折叠区（列：预测分、理由、共振分、涨跌%、封板、名称）
- 两区皆无：引导 `scan_horizon_outlook` + warm
- horizon 有、predict 无：提示重跑 Ops

- [ ] **Step 1: 实现 API 类型与页面**

- [ ] **Step 2: `cd frontend && npm run build`**

- [ ] **Step 3: 路线图 / smoke / spec 状态**

- [ ] **Step 4: `./scripts/check.sh` → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(radar): 展望页展示共振与规则预测双区

更新路线图与 smoke，完成展望加深收口。
EOF
)"
```

---

## Self-review

1. Spec 覆盖：合成卡、漏斗、first_time、rules_v1、upsert predict、GET、UI 双区、失败语义、docs → Task 1–5。  
2. 无 TBD；打分表与 spec 一致。  
3. `RadarPredictOut` / `score_predict_rows` / `resonance_scan_stats` 命名在任务间一致。

## Execution

实现前建议 worktree：`feat/radar-horizon-deepen`。
