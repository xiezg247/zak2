# notes 只读工具 + skill.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 增加 `list_note_symbols` / `get_stock_notes` 只读工具与 `notes/skill.py`（按 vt_symbol 分流）。

**Architecture:** 逻辑进 `ai_read_tools`；`ai_tools` 委托；skill 有标的则聚合，否则列表。

**Tech Stack:** notes service、Pydantic model_dump、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-notes-readonly-skill-design.md`

## Global Constraints

- 只改 zak2；不改 zak；不改 REST notes 路径
- 写操作不进 skill / 不进 WRITE 以外的旁路
- Commit 仅用户明确要求时（默认跳过）
- 不打真网

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/ai_read_tools.py` | `list_note_symbols` / `get_stock_notes` |
| `backend/app/services/ai_tools.py` | 注册两工具 |
| `backend/app/skills/notes/skill.py` | **新建** 分流 |
| `backend/app/skills/notes/SKILL.md` | 文档表 |
| `backend/tests/test_ai_read_tools.py` | 扩展测 |
| `backend/tests/test_ai_tools.py` / `test_ai_tools_skills.py` / `test_skills_catalog.py` | 工具名与 runnable |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: `ai_read_tools` 两函数 + ai_tools 注册

**Files:**
- Modify: `backend/app/services/ai_read_tools.py`
- Modify: `backend/app/services/ai_tools.py`
- Modify: `backend/tests/test_ai_read_tools.py`
- Modify: `backend/tests/test_ai_tools.py`

**Interfaces:**
```python
def list_note_symbols(db, user_id, args) -> dict:
    # limit 1..50 default 30
    # notes.list_note_symbols → dump → {"count", "symbols"}

def get_stock_notes(db, user_id, args) -> dict:
    # raw = vt_symbol or symbol; missing → {"error": "..."}
    # entry_limit 1..50 default 20
    # get_memo + list_entries → {"memo", "entries", "entry_count"}
```

- [ ] **Step 1: 写失败单测**

```python
# 追加 test_ai_read_tools.py
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services import ai_read_tools as art


def test_list_note_symbols_limit() -> None:
    items = [
        SimpleNamespace(
            model_dump=lambda: {"vt_symbol": f"{i}.SSE", "memo_preview": "", "entry_count": 0}
        )
        for i in range(5)
    ]
    with patch.object(art, "notes") as n:
        n.list_note_symbols.return_value = items
        out = art.list_note_symbols(MagicMock(), "u", {"limit": 2})
    assert out["count"] == 2
    assert len(out["symbols"]) == 2


def test_get_stock_notes_requires_symbol() -> None:
    out = art.get_stock_notes(MagicMock(), "u", {})
    assert "error" in out


def test_get_stock_notes_ok() -> None:
    memo = SimpleNamespace(model_dump=lambda: {"vt_symbol": "600519.SSE", "body": "x"})
    entries = [SimpleNamespace(model_dump=lambda: {"id": 1, "body": "e"})]
    with patch.object(art, "notes") as n:
        n.get_memo.return_value = memo
        n.list_entries.return_value = entries
        out = art.get_stock_notes(MagicMock(), "u", {"vt_symbol": "600519.SSE", "entry_limit": 10})
    assert out["memo"]["body"] == "x"
    assert out["entry_count"] == 1
    n.list_entries.assert_called_once()
```

若 `Note*Out` 是 pydantic，测里可直接构造真实 schema 对象代替 SimpleNamespace。

- [ ] **Step 2: 跑测确认失败**

Run: `cd backend && python -m pytest tests/test_ai_read_tools.py -k note -v`  
Expected: FAIL

- [ ] **Step 3: 实现 helper**

```python
# ai_read_tools.py
from app.services import notes  # 与 market 等并列

def list_note_symbols(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    limit = max(1, min(int(args.get("limit") or 30), 50))
    rows = notes.list_note_symbols(db, user_id)[:limit]
    symbols = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in rows]
    return {"count": len(symbols), "symbols": symbols}


def get_stock_notes(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("vt_symbol") or args.get("symbol") or "").strip()
    if not raw:
        return {"error": "需要 vt_symbol 或 symbol，例如 600519.SSE"}
    entry_limit = max(1, min(int(args.get("entry_limit") or 20), 50))
    memo = notes.get_memo(db, user_id, raw)
    entries = notes.list_entries(db, user_id, raw, limit=entry_limit)
    memo_d = memo.model_dump() if hasattr(memo, "model_dump") else dict(memo)
    entry_ds = [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in entries]
    return {"memo": memo_d, "entries": entry_ds, "entry_count": len(entry_ds)}
```

确认 `notes.list_entries` 签名含 `limit`（已有）。

- [ ] **Step 4: ai_tools 注册**

```python
def _list_note_symbols(db, user_id, args):
    from app.services import ai_read_tools
    return ai_read_tools.list_note_symbols(db, user_id, args)

def _get_stock_notes(db, user_id, args):
    from app.services import ai_read_tools
    return ai_read_tools.get_stock_notes(db, user_id, args)

# TOOL_HANDLERS 增加两者
# TOOL_DEFINITIONS 增加 function schema（required: get_stock_notes 要 vt_symbol 可选写在 description）
# 不进 WRITE_TOOL_NAMES
```

更新 `test_ai_tools.py` 期望的只读工具名集合，加入 `list_note_symbols`、`get_stock_notes`。

- [ ] **Step 5: 跑测**

```bash
cd backend && python -m pytest tests/test_ai_read_tools.py tests/test_ai_tools.py -v
```

Expected: PASS

- [ ] **Step 6: Commit（仅用户要求时）**

```bash
git add backend/app/services/ai_read_tools.py backend/app/services/ai_tools.py backend/tests/
git commit -m "$(cat <<'EOF'
feat(ai): 增加 notes 只读工具 list/get

EOF
)"
```

---

### Task 2: `notes/skill.py` + SKILL.md + catalog 测

**Files:**
- Create: `backend/app/skills/notes/skill.py`
- Modify: `backend/app/skills/notes/SKILL.md`
- Modify: `backend/tests/test_ai_read_tools.py` / `test_skills_catalog.py` / `test_ai_tools_skills.py`

**Interfaces:**
```python
def run(ctx, args):
    args = args or {}
    if str(args.get("vt_symbol") or args.get("symbol") or "").strip():
        return ai_read_tools.get_stock_notes(ctx.db, ctx.user_id, args)
    return ai_read_tools.list_note_symbols(ctx.db, ctx.user_id, args)
```

- [ ] **Step 1: 写失败测**

```python
def test_notes_runnable() -> None:
    from app.services.skills_catalog import list_skills
    m = {s["id"]: s for s in list_skills()}
    assert m["notes"]["runnable"] is True


def test_run_skill_notes_list() -> None:
    from app.services.ai_tools import execute_tool, WRITE_TOOL_NAMES
    assert "list_note_symbols" not in WRITE_TOOL_NAMES
    assert "get_stock_notes" not in WRITE_TOOL_NAMES
    with patch("app.services.ai_read_tools.list_note_symbols", return_value={"count": 0, "symbols": []}) as m:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "notes"})
    assert "symbols" in out or "count" in out
    m.assert_called_once()


def test_run_skill_notes_stock() -> None:
    from app.services.ai_tools import execute_tool
    with patch("app.services.ai_read_tools.get_stock_notes", return_value={"memo": {}, "entries": [], "entry_count": 0}) as m:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "notes", "vt_symbol": "600519.SSE"})
    assert "memo" in out
    m.assert_called_once()
```

- [ ] **Step 2: 实现 skill.py + SKILL.md**

SKILL.md 表增加：

```markdown
| list_note_symbols | 列出有笔记的标的 |
| get_stock_notes | 读备忘 + 近期流水 |
| run_skill | skill_id=notes；有 vt_symbol 则聚合，否则列表 |
```

- [ ] **Step 3: 跑测**

```bash
cd backend && python -m pytest tests/test_ai_read_tools.py tests/test_skills_catalog.py tests/test_ai_tools_skills.py tests/test_ai_tools.py -v
```

Expected: PASS（若 catalog 测仍断言 notes runnable False，改为 True）

- [ ] **Step 4: Commit（仅用户要求时）**

```bash
git add backend/app/skills/notes/ backend/tests/
git commit -m "$(cat <<'EOF'
feat(ai): notes skill 只读分流

EOF
)"
```

---

### Task 3: 文档

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap** — Skills：五 skill 均可 run（含 notes）；建议下一刀 B 站 / Docker 等。

- [ ] **Step 2: smoke** — AI：`list_note_symbols` / `get_stock_notes` 或 `run_skill notes`。

- [ ] **Step 3: 相关测**

```bash
cd backend && python -m pytest tests/test_ai_read_tools.py tests/test_skills_catalog.py tests/test_ai_tools_skills.py -q
```

- [ ] **Step 4: Commit（仅用户要求时）**

```bash
git add docs/gap-vs-desktop.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 记录 notes 只读 skill

EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| list_note_symbols / get_stock_notes | 1 |
| ai_tools 非写 | 1 |
| notes/skill 分流 | 2 |
| runnable / SKILL.md | 2 |
| gap / smoke | 3 |

## Placeholder scan

无 TBD；`list_entries` 的 `limit` 参数以实现签名为准。
