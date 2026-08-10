# 情绪周期加深（阈值 + 缓存 + warm）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 全局可调情绪阈值（`app.meta`）+ 短 TTL 缓存 + 可跑 `warm_market_summary`；Market 可编辑。

**Architecture:** `emotion_thresholds` 读写 meta → `emotion_cycle_cache` TTL → `build_emotion_cycle(force=)` 走缓存 → warm job 注册 → Market/Ops UI。

**Tech Stack:** FastAPI、app.meta、可选 Redis、Vue MarketView/OpsView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-07-emotion-cycle-deepen-design.md`

## Global Constraints

- 只改 zak2；不改 zak；全局一份阈值（非 per-user）
- Commit 仅用户明确要求时（默认跳过）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/emotion_thresholds.py` | load/save/reset/merge/clamp |
| `backend/app/services/emotion_cycle_cache.py` | get/set/invalidate（Redis+内存） |
| `backend/app/services/emotion_cycle.py` | `build_emotion_cycle` 接 thresholds + cache |
| `backend/app/services/ops_warm_market.py` | `warm_market_summary` |
| `backend/app/schemas/market.py` | ThresholdsOut / Put |
| `backend/app/api/v1/market.py` | GET/PUT/reset endpoints |
| `backend/app/services/ops_catalog.py` / `ops_runners.py` / `scheduler_defaults.py` | 注册 warm |
| `backend/tests/test_emotion_thresholds.py` / `test_emotion_cycle_cache.py` / 扩展 | 单测 |
| `frontend/src/api/market.ts` / `MarketView.vue` / `OpsView.vue` | UI |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: emotion_thresholds 服务

**Files:**
- Create: `backend/app/services/emotion_thresholds.py`
- Create: `backend/tests/test_emotion_thresholds.py`

**Interfaces:**
- `META_KEY = "emotion_cycle_thresholds"`
- `THRESHOLDS_FIELDS`：与 `emotion_cycle.Thresholds` 字段一致
- `thresholds_to_dict(t: Thresholds) -> dict`
- `merge_thresholds(base: Thresholds, patch: dict) -> Thresholds` — 只认已知键；夹逼（如 int≥0、up_ratio 0–1、fear 0–100）
- `load_thresholds(db) -> tuple[Thresholds, bool]` — `(effective, is_default)`；无 meta / 非法 JSON → 默认且 `is_default=True`
- `save_thresholds(db, patch: dict) -> Thresholds` — merge 当前 → 写 meta（ON CONFLICT）→ 返回生效
- `reset_thresholds(db) -> Thresholds` — `DELETE FROM app.meta WHERE key=:k` → 返回默认

复用 `emotion_cycle.Thresholds` / `DEFAULT_THRESHOLDS`（可从 emotion_cycle import，避免重复定义）。

- [ ] **Step 1: 写失败单测**

```python
from app.services.emotion_cycle import DEFAULT_THRESHOLDS
from app.services import emotion_thresholds as et


def test_merge_partial() -> None:
    t = et.merge_thresholds(DEFAULT_THRESHOLDS, {"recession_limit_down": 30})
    assert t.recession_limit_down == 30
    assert t.ice_max_boards == DEFAULT_THRESHOLDS.ice_max_boards


def test_load_default_when_empty() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    t, is_def = et.load_thresholds(db)
    assert is_def is True
    assert t == DEFAULT_THRESHOLDS
```

- [ ] **Step 2: RED → 实现 → GREEN**

- [ ] **Step 3: Commit** — 跳过

---

### Task 2: cache + build_emotion_cycle 接入

**Files:**
- Create: `backend/app/services/emotion_cycle_cache.py`
- Modify: `backend/app/services/emotion_cycle.py`
- Create/Modify: `backend/tests/test_emotion_cycle_cache.py`

**Interfaces:**
- `CACHE_KEY = "zak2:emotion_cycle:v1"`
- `cache_ttl_sec() -> int` — env `EMOTION_CYCLE_CACHE_TTL_SEC` 默认 60，夹逼 5–600
- `cache_get() -> dict | None`
- `cache_set(payload: dict) -> None`
- `cache_invalidate() -> None`
- 实现：先试 Redis（`get_quote_store` 的 client 若 available）；否则模块级 `_mem: tuple[float, dict] | None`（monotonic 过期）

`build_emotion_cycle(db, *, force: bool = False) -> dict`:
1. if not force: hit = cache_get(); if hit: return hit（可打标 `cached: True` 可选，spec 未强制）
2. `thresholds, _ = load_thresholds(db)`；原逻辑里 `t = DEFAULT_THRESHOLDS` 改为 `t = thresholds`
3. 算完 `cache_set(out)`；return out

- [ ] **Step 1: 单测**

```python
def test_mem_cache_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("EMOTION_CYCLE_CACHE_TTL_SEC", "60")
    # force clear
    from app.services import emotion_cycle_cache as c
    c.cache_invalidate()
    assert c.cache_get() is None
    c.cache_set({"stage": "ice"})
    assert c.cache_get()["stage"] == "ice"
    c.cache_invalidate()
    assert c.cache_get() is None


def test_build_uses_cache(monkeypatch) -> None:
    from app.services import emotion_cycle as ec
    from app.services import emotion_cycle_cache as c
    c.cache_invalidate()
    c.cache_set({"stage": "ice", "stage_label": "冰点", "cached_stub": True})
    db = MagicMock()
    out = ec.build_emotion_cycle(db, force=False)
    assert out.get("cached_stub") is True
    out2 = ec.build_emotion_cycle(db, force=True)
    # force 应重算，不会保留 cached_stub（除非偶然）
    assert "cached_stub" not in out2 or out2.get("stage") is not None
```

（force=True 的断言可改为 patch `_breadth_from_redis` 返回可控值，避免依赖 Redis。）

更稳妥的 force 测：

```python
def test_build_force_bypasses_cache(monkeypatch) -> None:
    from app.services import emotion_cycle as ec
    from app.services import emotion_cycle_cache as c
    c.cache_set({"stage": "ice", "from_cache": True})
    db = MagicMock()
    with (
        patch.object(ec, "_breadth_from_redis", return_value=None),
        patch.object(ec, "_ladder_rows", return_value=[]),
        patch.object(ec, "_index_above_ma5", return_value=None),
        patch.object(ec, "load_thresholds", return_value=(ec.DEFAULT_THRESHOLDS, True)),
    ):
        # import load_thresholds from emotion_thresholds in emotion_cycle
        out = ec.build_emotion_cycle(db, force=True)
    assert out.get("from_cache") is not True
    assert "stage" in out
```

注意：`emotion_cycle` 应 `from app.services.emotion_thresholds import load_thresholds`。

- [ ] **Step 2: 实现 cache + 改 build**

- [ ] **Step 3: GREEN** — 相关 pytest PASS

- [ ] **Step 4: Commit** — 跳过

---

### Task 3: API + warm job + 注册

**Files:**
- Modify: `backend/app/schemas/market.py`
- Modify: `backend/app/api/v1/market.py`
- Create: `backend/app/services/ops_warm_market.py`
- Modify: `ops_catalog.py` / `ops_runners.py` / `scheduler_defaults.py`
- Modify: tests（catalog + 可选 API）

**Schemas:**

```python
class EmotionThresholdsOut(BaseModel):
    # all Thresholds fields
    is_default: bool = True

class EmotionThresholdsPut(BaseModel):
    # all fields Optional
    recession_limit_down: int | None = None
    ...
```

**API:**
- GET thresholds → `EmotionThresholdsOut(**thresholds_to_dict(t), is_default=is_def)`
- PUT → save；`cache_invalidate()`；返回 Out
- POST reset → reset；invalidate；返回 Out

**warm:**

```python
def warm_market_summary(db: Session) -> dict:
    snap = build_emotion_cycle(db, force=True)
    save_job_run_meta(...)
    return {
        "success": True,
        "message": f"已预热情绪周期：{snap['stage_label']}",
        "stage": snap["stage"],
        "stage_label": snap["stage_label"],
        "source": snap.get("source"),
    }
```

注册：`RUNNABLE` 加 `warm_market_summary`；runner 映射；`DEFAULT_CRON` `{"hour": 9, "minute": 25, "day_of_week": "mon-fri"}`；catalog 描述更新。

save 后必须 `emotion_cycle_cache.cache_invalidate()`。

- [ ] **Step 1–3: 实现 + 单测 catalog 含 warm + save invalidate**

```python
def test_save_invalidates_cache(monkeypatch) -> None:
    ...
    c.cache_set({"stage": "x"})
    et.save_thresholds(db, {"recession_limit_down": 25})
    # save_thresholds 内或 API 层 invalidate；若在 API 层，测 API；推荐 service 层 save/reset 末尾 invalidate
    assert c.cache_get() is None
```

（推荐：`save_thresholds` / `reset_thresholds` 末尾调用 `cache_invalidate`，避免 API 遗漏。）

- [ ] **Step 4: GREEN**

- [ ] **Step 5: Commit** — 跳过

---

### Task 4: Market + Ops UI

**Files:**
- Modify: `frontend/src/api/market.ts`
- Modify: `frontend/src/views/MarketView.vue`
- Modify: `frontend/src/views/OpsView.vue`

**API client:**

```typescript
export type EmotionThresholds = { ...fields; is_default: boolean }
emotionThresholds(): Promise<EmotionThresholds>
putEmotionThresholds(body: Partial<...>): Promise<EmotionThresholds>
resetEmotionThresholds(): Promise<EmotionThresholds>
```

**MarketView:**
- 情绪卡片下可折叠「判定阈值」
- 打开时 GET 填表；保存 PUT；恢复默认 POST reset
- 成功后 `refresh()` overview

主要字段（不必一次露全部，至少）：  
`recession_limit_down, ice_limit_down, climax_limit_up, startup_limit_up, fear_greed_overheat, hysteresis_enabled`  
其余可一并绑定若表单空间允许。

**OpsView:**
- 快捷按钮「预热情绪周期」→ `runJob('warm_market_summary', true)`（走 async runJob 分支，与其它 job 相同）
- 文案一句：短 TTL 缓存

- [ ] **Step 1–3: UI + `npm run build`**

- [ ] **Step 4: Commit** — 跳过

---

### Task 5: 文档 + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`
- Optional: `.env.example` 加 `EMOTION_CYCLE_CACHE_TTL_SEC`

- [ ] **Step 1: gap** — 情绪周期行改为：全局可调阈值 + 短 TTL 缓存 + warm job（仍薄）

- [ ] **Step 2: smoke** — Market 可改阈值并保存；Ops 可预热情绪周期

- [ ] **Step 3:**

```bash
cd backend && python -m pytest -q
cd frontend && npm run build
```

- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage（自检）

| Spec 项 | Task |
|---------|------|
| thresholds meta API | 1+3 |
| cache TTL + force | 2 |
| warm + RUNNABLE 09:25 | 3 |
| Market/Ops UI | 4 |
| gap/smoke/验收 | 5 |
| 非目标 per-user / 输入加深 | 未实现（符合） |
