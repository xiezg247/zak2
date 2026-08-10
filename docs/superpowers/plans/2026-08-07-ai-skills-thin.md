# AI Skills 薄接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 内置 Web 向 SKILL.md；Agent 经 `list_skills` / `read_skill` 只读加载。

**Architecture:** `skills_catalog` 扫 `app/skills/*/SKILL.md` → 挂入 `ai_tools` 只读工具；无 REST/UI。

**Tech Stack:** FastAPI 侧纯文件 IO、现有 tool-calling、pytest、YAML-ish frontmatter。

**Spec:** `docs/superpowers/specs/2026-08-07-ai-skills-thin-design.md`

## Global Constraints

- 只改 zak2；不改 zak / 不跑桌面 Python Skill
- 只读文件；无 Skills 面板 / 无 SKILLS_DIR
- Commit 仅用户明确要求时（默认跳过）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/skills/*/SKILL.md` ×5 | 内置说明 |
| `backend/app/services/skills_catalog.py` | list/read + 安全解析 |
| `backend/app/services/ai_tools.py` | 注册两个只读 tool |
| `backend/tests/test_skills_catalog.py` | catalog + 安全 |
| `backend/tests/test_ai_tools_skills.py`（或并入现有 ai tools 测） | tool 接线 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: skills_catalog + 5× SKILL.md

**Files:**
- Create: `backend/app/services/skills_catalog.py`
- Create: `backend/app/skills/{watchlist,market-emotion,screener,radar,notes}/SKILL.md`
- Create: `backend/tests/test_skills_catalog.py`

**Interfaces:**
- `MAX_SKILL_CHARS = 12000`
- `skills_root() -> Path`
- `list_skills() -> list[dict]`  # id, name, description；按 id 排序
- `read_skill(skill_id: str) -> dict`  # id, name, description, content；非法 → ValueError 中文
- `_parse_frontmatter(text) -> tuple[dict, str]`
- `_safe_skill_dir(skill_id) -> Path`  # regex `[a-z0-9][a-z0-9_-]*`；resolve 须在 root 下

- [ ] **Step 1: 失败单测**

```python
from app.services.skills_catalog import list_skills, read_skill

def test_list_has_five() -> None:
    ids = {s["id"] for s in list_skills()}
    assert ids == {"watchlist", "market-emotion", "screener", "radar", "notes"}

def test_read_watchlist() -> None:
    doc = read_skill("watchlist")
    assert doc["id"] == "watchlist"
    assert "get_watchlist" in doc["content"]

def test_reject_traversal() -> None:
    import pytest
    with pytest.raises(ValueError):
        read_skill("../secrets")
    with pytest.raises(ValueError):
        read_skill("nope")
```

- [ ] **Step 2: RED** — `cd backend && python -m pytest tests/test_skills_catalog.py -v`

- [ ] **Step 3: 实现 catalog + 5 个短 SKILL.md**（正文含工具表；写操作注明确认）

示例 `watchlist/SKILL.md`：

```markdown
---
name: watchlist
description: 自选查看与加减；写操作须用户确认
---

# 自选

触发：自选、加自选、删自选。

| 工具 | 用途 |
|------|------|
| get_watchlist | 列出自选 |
| add_watchlist | 加入（须确认卡） |
| remove_watchlist | 移除（须确认卡） |
```

- [ ] **Step 4: GREEN**

- [ ] **Step 5: Commit** — 跳过

---

### Task 2: 挂入 ai_tools

**Files:**
- Modify: `backend/app/services/ai_tools.py`
- Create or Modify: `backend/tests/test_ai_tools_skills.py`（或扩展已有 `test_ai_*.py`）

**Wiring:**
- `TOOL_DEFINITIONS` 追加 `list_skills`、`read_skill`
- `TOOL_HANDLERS`：handlers 忽略 db/user_id，调 catalog；`read_skill` 捕获 `ValueError` → `{"error": str(exc)}`
- `execute_tool` 路径走 handlers（非 write、非 mcp_）

```python
def _list_skills(db, user_id, args):
    from app.services import skills_catalog
    return {"skills": skills_catalog.list_skills()}

def _read_skill(db, user_id, args):
    from app.services import skills_catalog
    sid = str(args.get("skill_id") or "").strip()
    try:
        return skills_catalog.read_skill(sid)
    except ValueError as exc:
        return {"error": str(exc)}
```

- [ ] **Step 1: 单测** `execute_tool(..., "list_skills", {})` 含 watchlist；`read_skill` 未知 id 返回 error 键

- [ ] **Step 2–3: 实现 + pytest PASS**

- [ ] **Step 4: Commit** — 跳过

---

### Task 3: 文档 + 全量

**Files:**
- `docs/gap-vs-desktop.md`
- `docs/smoke-checklist.md`

- gap AI 行：内置 SKILL.md + list/read；仍无 Python Skill 运行时；下一刀另定
- smoke：Ai / 工具可 list_skills（或注明单测覆盖）

- [ ] **Step 1: 改文档**
- [ ] **Step 2: `cd backend && python -m pytest`**
- [ ] **Step 3: `cd frontend && npm run build`**（无前端改动亦回归）
- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage

| Spec | Task |
|------|------|
| catalog + 5 md + 安全 | 1 |
| Agent tools | 2 |
| docs + 验收 | 3 |

无 TBD。
