# 其余内置 Skill 只读 skill.py 补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 抽出 `ai_read_tools`，为 watchlist/screener/radar 补只读 `skill.py`，并让 market-emotion 走同一 helper。

**Architecture:** 将 `_get_watchlist` / emotion / screening / radar 迁入 `ai_read_tools.py`；`ai_tools` 薄委托；各 `skill.py` 的 `run` 调用 helper；notes 不改。

**Tech Stack:** 现有 services、skill_runtime、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-skill-py-readonly-fill-design.md`

## Global Constraints

- 只改 zak2；不改 zak；不改 skill_runtime 超时语义
- 跳过 notes；写操作不进 skill
- Commit 仅用户明确要求时（默认跳过）
- 不打真网

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/ai_read_tools.py` | **新建** 四只读实现 |
| `backend/app/services/ai_tools.py` | `_get_*` 委托 |
| `backend/app/skills/watchlist/skill.py` | **新建** |
| `backend/app/skills/screener/skill.py` | **新建** |
| `backend/app/skills/radar/skill.py` | **新建** |
| `backend/app/skills/market-emotion/skill.py` | 改调 helper |
| `backend/app/skills/*/SKILL.md` | 补 run_skill 行（三目录） |
| `backend/tests/test_ai_read_tools.py` | **新建** helper/skill 测 |
| `backend/tests/test_skills_catalog.py` | runnable 断言扩展 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: 抽出 `ai_read_tools` + ai_tools 委托

**Files:**
- Create: `backend/app/services/ai_read_tools.py`
- Modify: `backend/app/services/ai_tools.py`
- Create: `backend/tests/test_ai_read_tools.py`（先测 helper 签名/委托；skill 测在 Task 2）

**Interfaces:**
- `get_watchlist(db, user_id, args: dict) -> Any`
- `get_market_emotion(db, user_id, args: dict) -> Any`
- `get_recent_screening(db, user_id, args: dict) -> Any`
- `get_radar_snapshot(db, user_id, args: dict) -> Any`
- 逻辑从现有 `_get_*` **原样搬迁**（含 import）

- [ ] **Step 1: 写失败测（委托后行为）**

```python
# backend/tests/test_ai_read_tools.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import ai_read_tools as art
from app.services.ai_tools import execute_tool


def test_get_market_emotion_shape() -> None:
    db = MagicMock()
    with (
        patch.object(art.market, "load_emotion", return_value={"phase": "冰点"}),
        patch.object(art.market, "market_overview", return_value={"ok": 1}),
    ):
        out = art.get_market_emotion(db, "u", {})
    assert out["emotion"]["phase"] == "冰点"
    assert out["overview"] == {"ok": 1}


def test_ai_tools_delegates_emotion() -> None:
    with patch("app.services.ai_read_tools.get_market_emotion", return_value={"emotion": {}, "overview": {}}) as m:
        raw = execute_tool(MagicMock(), "u", "get_market_emotion", {})
    assert "emotion" in raw
    m.assert_called_once()
```

（`ai_read_tools` 需 `from app.services import market` 等，测里 `art.market` 可用。）

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && python -m pytest tests/test_ai_read_tools.py -v`  
Expected: FAIL（模块不存在或未委托）

- [ ] **Step 3: 实现 `ai_read_tools.py`**

把 `ai_tools.py` 中 `_get_watchlist`、`_get_market_emotion`、`_get_recent_screening`、`_get_radar_snapshot` 函数体迁入，保留相同依赖 import。

- [ ] **Step 4: ai_tools 薄委托**

```python
def _get_watchlist(db, user_id, args):
    from app.services import ai_read_tools
    return ai_read_tools.get_watchlist(db, user_id, args)
# 同理 emotion / screening / radar
```

删除原函数体内联实现（避免重复）。

- [ ] **Step 5: 跑测**

```bash
cd backend && python -m pytest tests/test_ai_read_tools.py tests/test_ai_tools.py -v
```

Expected: PASS

- [ ] **Step 6: Commit（仅用户要求时）**

```bash
git add backend/app/services/ai_read_tools.py backend/app/services/ai_tools.py backend/tests/test_ai_read_tools.py
git commit -m "$(cat <<'EOF'
refactor(ai): 抽出只读工具 ai_read_tools

EOF
)"
```

---

### Task 2: 三个 skill.py + market-emotion 改道 + catalog/SKILL.md

**Files:**
- Create: `backend/app/skills/watchlist/skill.py`
- Create: `backend/app/skills/screener/skill.py`
- Create: `backend/app/skills/radar/skill.py`
- Modify: `backend/app/skills/market-emotion/skill.py`
- Modify: `backend/app/skills/watchlist/SKILL.md`、`screener/SKILL.md`、`radar/SKILL.md`
- Modify: `backend/tests/test_ai_read_tools.py`、`backend/tests/test_skills_catalog.py`

**Interfaces:**
```python
# 各 skill.py 模板
def run(ctx, args):
    return ai_read_tools.get_*(ctx.db, ctx.user_id, args or {})
```

- [ ] **Step 1: 追加失败测**

```python
def test_runnable_flags() -> None:
    from app.services.skills_catalog import list_skills
    m = {s["id"]: s for s in list_skills()}
    assert m["watchlist"]["runnable"] is True
    assert m["screener"]["runnable"] is True
    assert m["radar"]["runnable"] is True
    assert m["market-emotion"]["runnable"] is True
    assert m["notes"]["runnable"] is False


def test_run_skill_watchlist_mocked() -> None:
    from app.services.ai_tools import execute_tool
    with patch("app.services.ai_read_tools.get_watchlist", return_value={"count": 0, "items": []}) as m:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "watchlist", "limit": 5})
    assert "items" in out or "count" in out
    m.assert_called_once()
```

（`run_skill` → runtime → 真 skill.py → helper；mock helper 即可验证链路。若 mock 路径需 patch `app.skills...` 所 import 的名字，按 skill 内 import 方式调整。）

同类可对 screener/radar 各一条，或一条 parametrize。

- [ ] **Step 2: 实现三 skill + 改 emotion**

```python
# watchlist/skill.py
from app.services import ai_read_tools
def run(ctx, args):
    return ai_read_tools.get_watchlist(ctx.db, ctx.user_id, args or {})
```

screener → `get_recent_screening`；radar → `get_radar_snapshot`；market-emotion → `get_market_emotion`。

- [ ] **Step 3: SKILL.md**

三目录工具表增加：

```markdown
| run_skill | skill_id=本目录 id，执行 skill.py（只读） |
```

- [ ] **Step 4: 跑测**

```bash
cd backend && python -m pytest tests/test_ai_read_tools.py tests/test_skills_catalog.py tests/test_ai_tools_skills.py tests/test_skill_runtime.py -v
```

Expected: PASS

- [ ] **Step 5: Commit（仅用户要求时）**

```bash
git add backend/app/skills/ backend/tests/test_ai_read_tools.py backend/tests/test_skills_catalog.py
git commit -m "$(cat <<'EOF'
feat(ai): watchlist/screener/radar 只读 skill.py

EOF
)"
```

---

### Task 3: 文档

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap** — Skills 行：四 skill 可 `run_skill`；notes 仍无。建议下一刀：notes 只读+skill 或 B 站/Docker。

- [ ] **Step 2: smoke** — AI 节：`run_skill` 对 watchlist/screener/radar/market-emotion 可用（可一条合并）。

- [ ] **Step 3: 相关测**

```bash
cd backend && python -m pytest tests/test_ai_read_tools.py tests/test_skills_catalog.py tests/test_ai_tools_skills.py -q
```

- [ ] **Step 4: Commit（仅用户要求时）**

```bash
git add docs/gap-vs-desktop.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 记录四 skill 可 run_skill

EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| ai_read_tools 四函数 + 委托 | 1 |
| watchlist/screener/radar skill.py | 2 |
| market-emotion 改道 | 2 |
| runnable / notes False | 2 |
| gap / smoke | 3 |
| notes / runtime 改动 | 非目标 |

## Placeholder scan

无 TBD；mock 路径以实现时 import 为准。
