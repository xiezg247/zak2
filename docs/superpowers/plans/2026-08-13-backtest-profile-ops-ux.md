# 回测画像填参与失败 Ops 引导 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PROFILES 带均线/资金；chip 点选填表；日 K 类错误旁链 `/ops`。

**Architecture:** 扩展 `PROFILES` + `StrategyProfileOut`；BacktestView 可点 chip 与条件 RouterLink。

**Tech Stack:** FastAPI/Pydantic、Vue 3、vue-router。

**Spec:** `docs/superpowers/specs/2026-08-13-backtest-profile-ops-ux-design.md`

## Global Constraints

- 不改双均线撮合逻辑；不自动开跑；不深链执行 job
- Commit 简体中文；不 push

---

### Task 1: 后端 PROFILES + 前端 chip/Ops 链

**Files:**
- Modify: `backend/app/services/backtest_engine.py`
- Modify: `backend/app/schemas/backtest.py`
- Create: `backend/tests/test_backtest_profiles.py`
- Modify: `frontend/src/api/backtest.ts`
- Modify: `frontend/src/views/BacktestView.vue`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_backtest_profiles.py
from app.schemas.backtest import StrategyProfileOut
from app.services.backtest_engine import PROFILES


def test_profiles_have_window_and_capital() -> None:
    assert len(PROFILES) >= 4
    for raw in PROFILES:
        p = StrategyProfileOut.model_validate(raw)
        assert 2 <= p.fast_window < p.slow_window <= 250
        assert p.capital > 0
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_backtest_profiles.py -q
```

Expected: FAIL（缺字段）

- [ ] **Step 3: 扩展 schema 与 PROFILES**

`StrategyProfileOut`：

```python
class StrategyProfileOut(BaseModel):
    profile_id: str
    name: str
    description: str
    fast_window: int
    slow_window: int
    capital: float
```

`PROFILES` 按 spec 初值：

```python
PROFILES = (
    {"profile_id": "ultra_short", "name": "极致短线", "description": "打板/半路，持仓短", "fast_window": 3, "slow_window": 8, "capital": 100_000},
    {"profile_id": "short_swing", "name": "短线波段", "description": "放量突破为主", "fast_window": 5, "slow_window": 20, "capital": 100_000},
    {"profile_id": "medium_watch", "name": "中线观察", "description": "趋势跟踪辅助", "fast_window": 10, "slow_window": 30, "capital": 100_000},
    {"profile_id": "trend", "name": "趋势", "description": "均线趋势，持仓更长", "fast_window": 20, "slow_window": 60, "capital": 100_000},
)
```

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_backtest_profiles.py tests/test_backtest_engine.py -q
```

Expected: PASS

- [ ] **Step 5: 前端类型 + BacktestView**

`StrategyProfile` 增加三字段。

```typescript
import { RouterLink } from 'vue-router'

const activeProfileId = ref('')

function applyProfile(p: StrategyProfile) {
  fast.value = p.fast_window
  slow.value = p.slow_window
  capital.value = p.capital
  activeProfileId.value = p.profile_id
}

const showOpsLink = computed(() => /日 K|Ops|补全/.test(error.value))
```

模板：

```vue
<section class="profiles" v-if="profiles.length">
  <button
    v-for="p in profiles"
    :key="p.profile_id"
    type="button"
    class="chip"
    :class="{ on: activeProfileId === p.profile_id }"
    :title="p.description"
    @click="applyProfile(p)"
  >
    {{ p.name }}
  </button>
</section>

<p v-if="error" class="err">
  {{ error }}
  <RouterLink v-if="showOpsLink" to="/ops" class="draft-link">去 Ops 补全日 K</RouterLink>
</p>
```

样式：`.chip.on` 边框高亮；`.draft-link` 对齐 Feed（`color: var(--brand)`）。

- [ ] **Step 6: 前端构建**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/backtest_engine.py \
  backend/app/schemas/backtest.py \
  backend/tests/test_backtest_profiles.py \
  frontend/src/api/backtest.ts \
  frontend/src/views/BacktestView.vue
git commit -m "$(cat <<'EOF'
feat(backtest): 画像 chip 填参并引导日 K 不足去 Ops

PROFILES 携带均线/资金；失败文案可跳转运维页。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

```markdown
- [ ] `/backtest` 点画像 chip 可写入快/慢均线与资金并高亮；日 K 不足类错误旁可见「去 Ops 补全日 K」链到 `/ops`
```

- [ ] **Step 2: roadmap #34**

```markdown
34. ~~回测画像填参与失败 Ops 引导~~（已完成 → [spec](./superpowers/specs/2026-08-13-backtest-profile-ops-ux-design.md)）
```

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: `OK：测试与构建通过`

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs: 记录回测画像填参与 Ops 引导完成

更新 smoke 与路线图 #34。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| PROFILES + schema | 1 |
| 单测 | 1 |
| chip 填参 + 高亮 | 1 |
| Ops 链 | 1 |
| smoke + #34 | 2 |
| 不自动开跑 | Global |

无 TBD。
