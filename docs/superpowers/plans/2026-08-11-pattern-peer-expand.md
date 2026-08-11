# 形态扩因子 + 对标扩维 + 找同类 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 新增 2 日 K 形态；对标扩为五维权重；Hub 结果行「找同类」。

**Architecture:** `pattern_rules` 注册 matcher；`reference_peer` 一次拉 20 日涨跌图并切片算 5/20 日动量 + 换手分；Hub 切 peer Tab 复用现有跑法。

**Tech Stack:** FastAPI、现有 pattern_screen / Tushare peer、Vue ScreenerHubView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-11-pattern-peer-expand-design.md`

## Global Constraints

- 只改 zak2；不改 zak；不 import vnpy_*
- 不做 MCP 形态、配方扩维、权重 UI、中文别名
- Commit 仅用户明确要求时（默认跳过）
- 默认权重：industry 0.30 / valuation 0.25 / momentum_5d 0.15 / momentum_20d 0.15 / turnover 0.15

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/pattern_rules.py` | `match_platform_break` / `match_pullback_ma20` + META |
| `backend/tests/test_pattern_rules.py` | 新形态单测 |
| `backend/app/services/reference_peer.py` | 五维评分与字段 |
| `backend/app/schemas/screener.py` | 可选 `weights` on `ReferencePeerRequest` |
| `backend/tests/test_reference_peer.py` | 评分 + mock 跑法 |
| `frontend/src/views/ScreenerHubView.vue` | 「找同类」 |
| `docs/gap-vs-desktop.md` / `docs/smoke-checklist.md` | 文档 |

---

### Task 1: 两个新形态

**Files:**
- Modify: `backend/app/services/pattern_rules.py`
- Modify: `backend/tests/test_pattern_rules.py`

**Interfaces:**
```python
def match_platform_break(series: BarSeries) -> PatternMatch | None: ...
def match_pullback_ma20(series: BarSeries) -> PatternMatch | None: ...
# PATTERN_MATCHERS + PATTERN_META 含 platform_break / pullback_ma20
```

- [ ] **Step 1: 写失败单测**

在 `test_pattern_rules.py` 追加（构造函数可沿用 `_series`，平台/突破需自定义 highs/lows/volumes）：

```python
from app.services.pattern_rules import match_platform_break, match_pullback_ma20

def test_platform_break_match() -> None:
    # 40+ bars: flat 15-day platform then breakout with volume
    n = 50
    closes = [10.0] * (n - 2) + [10.5, 10.8]
    highs = [10.2] * (n - 2) + [10.6, 10.9]
    lows = [9.9] * (n - 2) + [10.4, 10.5]
    vols = [1000.0] * (n - 5) + [1000.0, 1000.0, 1000.0, 1000.0, 2500.0]
    # 平台窗振幅需 ≤8%；末收 > 平台高
    m = match_platform_break(BarSeries(closes=closes, highs=highs, lows=lows, volumes=vols))
    assert m is not None
    assert m.score > 0


def test_platform_break_reject_no_breakout() -> None:
    closes = [10.0] * 50
    highs = [10.2] * 50
    lows = [9.9] * 50
    assert match_platform_break(BarSeries(closes=closes, highs=highs, lows=lows, volumes=[1000.0] * 50)) is None


def test_pullback_ma20_match() -> None:
    # rising then dip near MA20 then close >= prev
    closes = [10.0 + i * 0.05 for i in range(50)]
    # force a recent low near MA20 — adjust last 10 bars carefully in implementation test
    ...
```

实现测试时以**可稳定命中**的序列为准；若构造困难，允许在测里对辅助函数做最小 monkeypatch，但优先纯序列。

- [ ] **Step 2: 跑测确认失败**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_pattern_rules.py -k "platform_break or pullback_ma20" -v
```

Expected: FAIL（函数未定义）

- [ ] **Step 3: 实现 matcher + 注册**

按 spec 规则实现 `match_platform_break`、`match_pullback_ma20`；挂入 `PATTERN_MATCHERS`；`PATTERN_META` 追加两项中文名/描述。

平台窗索引约定（实现写死并测）：

```python
# 示例：平台取 closes 的 [-17:-2] 对应 highs/lows；最新 bar = [-1]
platform_high = max(highs[-17:-2])
platform_low = min(lows[-17:-2])
amplitude = (platform_high - platform_low) / platform_low  # ≤ 0.08
breakout = closes[-1] > platform_high
vol_ratio = _volume_ratio(volumes)  # ≥ 1.2
```

回踩：

```python
ma20 = _ma(closes, 20)
# 近 10 日: any abs(lows[i]-ma20)/ma20 <= 0.02
# closes[-1] >= closes[-2]; vol_ratio <= 0.9; ma20 > ma60 if ma60
```

- [ ] **Step 4: 跑测绿**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_pattern_rules.py -v
```

Expected: PASS

- [ ] **Step 5: Commit（仅用户要求时）**

```bash
git add backend/app/services/pattern_rules.py backend/tests/test_pattern_rules.py
git commit -m "$(cat <<'EOF'
feat(screener): 新增平台突破与回踩 MA20 形态

EOF
)"
```

---

### Task 2: 对标五维

**Files:**
- Modify: `backend/app/services/reference_peer.py`
- Modify: `backend/app/schemas/screener.py`（可选 `weights: dict[str, float] | None = None`）
- Modify: `backend/tests/test_reference_peer.py`

**Interfaces:**
```python
_DEFAULT_WEIGHTS = {
    "industry": 0.30,
    "valuation": 0.25,
    "momentum_5d": 0.15,
    "momentum_20d": 0.15,
    "turnover": 0.15,
}

def turnover_score(ref_to: float, cand_to: float) -> float: ...
def resolve_weights(override: dict[str, float] | None) -> dict[str, float]: ...
def composite_similarity(
    *,
    val_score: float,
    mom5_score: float,
    mom20_score: float,
    turnover_s: float,
    weights: dict[str, float] | None = None,
) -> float: ...
```

- [ ] **Step 1: 写/改单测**

```python
def test_turnover_score() -> None:
    assert peer.turnover_score(2.0, 2.0) == 100.0
    assert peer.turnover_score(0, 0) == 50.0  # 缺数据中性


def test_scoring_helpers() -> None:
    assert peer.valuation_score(pe=20, mv=1000, ref_pe=20, ref_mv=1000) == 100.0
    assert peer.momentum_score(5.0, 5.0) == 100.0
    assert peer.composite_similarity(
        val_score=100, mom5_score=100, mom20_score=100, turnover_s=100
    ) == 100.0


def test_run_reference_peer_mocked() -> None:
    # _fetch_pct_maps 返回 20 张日图（可重复同一 dict）
    pct = [{"600519.SH": 1.0, "600000.SH": 1.2, "000001.SZ": -1.0}] * 20
    ...
    assert result["config"]["weights"]["momentum_20d"] == 0.15
    assert result["config"]["weights"]["turnover"] == 0.15
    assert "momentum_20d" in result["rows"][0]
```

- [ ] **Step 2: 跑测确认失败/需改**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_reference_peer.py -v
```

Expected: 旧 `composite_similarity` 签名导致 FAIL，或新断言 FAIL

- [ ] **Step 3: 实现**

1. 常量改为 `_DEFAULT_WEIGHTS`；删除旧三权重常量或保留为兼容别名。  
2. `turnover_score` / `resolve_weights`（缺键补默认；可选归一化到和为 1）。  
3. `composite_similarity` 五维。  
4. `run_reference_peer`：  
   - `pct_maps = _fetch_pct_maps(db, days=20)`  
   - `mom5 = cumulative_return(code, pct_maps[:5])`  
   - `mom20 = cumulative_return(code, pct_maps[:20])`  
   - 换手：`reference` / candidate 的 `turnover_rate`  
   - 行字段：`momentum_5d`、`momentum_20d`、`turnover_score`；hint 追加 20 日与换手句  
   - `config.weights` 用 resolve 后的字典  
5. Schema：`ReferencePeerRequest.weights: dict[str, float] | None = None`

- [ ] **Step 4: 跑测绿**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_reference_peer.py tests/test_pattern_rules.py -v
```

Expected: PASS

- [ ] **Step 5: Commit（仅用户要求时）**

```bash
git add backend/app/services/reference_peer.py backend/app/schemas/screener.py backend/tests/test_reference_peer.py
git commit -m "$(cat <<'EOF'
feat(screener): 对标增加 20 日动量与换手维度

EOF
)"
```

---

### Task 3: Hub「找同类」+ 文档

**Files:**
- Modify: `frontend/src/views/ScreenerHubView.vue`
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: 找同类**

在结果表「自选」旁：

```typescript
function findPeers(row: ScreenerResultRow) {
  const vt = String(row.vt_symbol || '').trim() || String(row.symbol || '').trim()
  if (!vt) return
  peerSymbol.value = vt.includes('.') ? vt : vt // 已有 vt 优先
  tab.value = 'peer'
  void runScreen()
}
```

模板：

```html
<button type="button" class="link" @click="findPeers(row)">找同类</button>
```

确保 `runScreen` 在 `tab==='peer'` 时用 `peerSymbol`（现有逻辑已如此）。

- [ ] **Step 2: `npm run build`**

```bash
cd /Users/xiezhigang/Projects/me/zak2/frontend && npm run build
```

Expected: exit 0

- [ ] **Step 3: 文档**

- gap 形态/对标行：6 形态 + 对标五维 + Hub 找同类  
- 建议下一刀：只读持仓/信号或其它  
- smoke：形态含平台突破/回踩 MA20；对标权重五维；结果行找同类  

- [ ] **Step 4: 相关测再跑**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_pattern_rules.py tests/test_reference_peer.py -v
```

- [ ] **Step 5: Commit（仅用户要求时）**

```bash
git add frontend/src/views/ScreenerHubView.vue docs/gap-vs-desktop.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
feat(screener): Hub 结果行支持找同类并对齐文档

EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| platform_break / pullback_ma20 | 1 |
| 五维对标 + weights | 2 |
| 找同类 | 3 |
| gap / smoke | 3 |
| MCP / 配方 / 别名 | 非目标 |

## Placeholder scan

无 TBD；`_fetch_pct_maps` 一次 20 日切片避免双请求；`composite_similarity` 签名变更已写入测试更新。
