# AI Skill Python 薄运行时 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 同进程加载 `skills/<id>/skill.py` 的 `run(ctx, args)`，暴露只读 `run_skill`；示范仅 `market-emotion`。

**Architecture:** `skill_runtime` 用 importlib + ThreadPoolExecutor 超时；`SkillContext(db, user_id)`；错误统一 `{error}`。`ai_tools` 注册 `run_skill`（不进写工具集）。`list_skills` 增加 `runnable`。

**Tech Stack:** importlib、concurrent.futures、SQLAlchemy Session、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-skill-python-runtime-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不真沙箱 / 不 subprocess；不搬桌面 skill
- 仅示范 `market-emotion`；写操作不经 skill
- Commit 仅用户明确要求时（默认跳过）
- 不打真网

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/skill_runtime.py` | **新建** Context + load_and_run |
| `backend/tests/test_skill_runtime.py` | **新建** runtime 单测 |
| `backend/app/skills/market-emotion/skill.py` | **新建** 示范 |
| `backend/app/skills/market-emotion/SKILL.md` | 补 run_skill 说明 |
| `backend/app/services/skills_catalog.py` | `runnable` 字段 |
| `backend/app/services/ai_tools.py` | `run_skill` 工具 |
| `backend/tests/test_ai_tools_skills.py` | 扩展工具测 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: `skill_runtime` + 单测

**Files:**
- Create: `backend/app/services/skill_runtime.py`
- Create: `backend/tests/test_skill_runtime.py`

**Interfaces:**
- `SKILL_TIMEOUT_SEC = 5`
- `@dataclass class SkillContext: db: Session; user_id: str`
- `run_skill_module(skill_id: str, ctx: SkillContext, args: dict | None = None) -> Any`
  - 成功：返回 `run` 的返回值  
  - 失败：返回 `{"error": str}`（非法 id、缺文件、无 `run`、超时、异常）  
  - 路径：复用 catalog 安全规则（可 import `_safe_skill_dir` 或复制同等校验；优先从 `skills_catalog` 导出 `safe_skill_dir` 若当前为私有则加公开别名 `resolve_skill_dir`）
- 加载：`importlib.util.spec_from_file_location(f"zak2_skill_{skill_id}", path)` → `exec_module` → 调 `mod.run(ctx, args or {})`
- 超时：`ThreadPoolExecutor(max_workers=1).submit(...).result(timeout=SKILL_TIMEOUT_SEC)`

- [ ] **Step 1: 若需公开 resolve，先在 catalog 加薄封装**

```python
# skills_catalog.py
def resolve_skill_dir(skill_id: str) -> Path:
    return _safe_skill_dir(skill_id)
```

- [ ] **Step 2: 写失败单测**

```python
# backend/tests/test_skill_runtime.py
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from app.services import skill_runtime as rt
from app.services.skill_runtime import SkillContext


def _ctx() -> SkillContext:
    return SkillContext(db=MagicMock(), user_id="u1")


def test_missing_skill_returns_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(rt, "skills_root_override", tmp_path)  # 若实现用 skills_catalog.skills_root
    # 更稳：monkeypatch skills_catalog.skills_root
    from app.services import skills_catalog as cat

    monkeypatch.setattr(cat, "skills_root", lambda: tmp_path)
    out = rt.run_skill_module("nope", _ctx(), {})
    assert "error" in out


def test_run_success(tmp_path, monkeypatch) -> None:
    from app.services import skills_catalog as cat

    monkeypatch.setattr(cat, "skills_root", lambda: tmp_path)
    d = tmp_path / "demo"
    d.mkdir()
    (d / "skill.py").write_text(
        "def run(ctx, args):\n    return {'ok': True, 'uid': ctx.user_id, 'n': args.get('n')}\n",
        encoding="utf-8",
    )
    out = rt.run_skill_module("demo", _ctx(), {"n": 3})
    assert out == {"ok": True, "uid": "u1", "n": 3}


def test_timeout_returns_error(tmp_path, monkeypatch) -> None:
    from app.services import skills_catalog as cat

    monkeypatch.setattr(cat, "skills_root", lambda: tmp_path)
    monkeypatch.setattr(rt, "SKILL_TIMEOUT_SEC", 0.2)
    d = tmp_path / "slow"
    d.mkdir()
    (d / "skill.py").write_text(
        "import time\ndef run(ctx, args):\n    time.sleep(2)\n    return {}\n",
        encoding="utf-8",
    )
    out = rt.run_skill_module("slow", _ctx(), {})
    assert "error" in out
    assert "超时" in str(out["error"]) or "timeout" in str(out["error"]).lower()


def test_illegal_id() -> None:
    out = rt.run_skill_module("../x", _ctx(), {})
    assert "error" in out
```

实现时：若不用 `skills_root_override`，统一 `monkeypatch.setattr(skills_catalog, "skills_root", ...)`，runtime 经 `resolve_skill_dir` / `skills_root` 解析。

- [ ] **Step 3: 跑测确认失败**

Run: `cd backend && python -m pytest tests/test_skill_runtime.py -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 4: 实现 `skill_runtime.py`**

```python
# backend/app/services/skill_runtime.py
from __future__ import annotations

import importlib.util
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.services import skills_catalog

_logger = logging.getLogger(__name__)

SKILL_TIMEOUT_SEC = 5.0


@dataclass
class SkillContext:
    db: Session
    user_id: str


def run_skill_module(skill_id: str, ctx: SkillContext, args: dict[str, Any] | None = None) -> Any:
    try:
        skill_dir = skills_catalog.resolve_skill_dir(skill_id)
    except ValueError as exc:
        return {"error": str(exc)}

    path = skill_dir / "skill.py"
    if not path.is_file():
        return {"error": f"skill 不可运行或不存在：{skill_id}"}

    try:
        spec = importlib.util.spec_from_file_location(f"zak2_skill_{skill_id}", path)
        if spec is None or spec.loader is None:
            return {"error": f"无法加载 skill：{skill_id}"}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        run_fn = getattr(mod, "run", None)
        if not callable(run_fn):
            return {"error": f"skill 缺少 run()：{skill_id}"}

        payload = dict(args or {})

        def _call() -> Any:
            return run_fn(ctx, payload)

        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_call)
            return fut.result(timeout=SKILL_TIMEOUT_SEC)
    except FuturesTimeout:
        return {"error": f"skill 执行超时（>{SKILL_TIMEOUT_SEC}s）：{skill_id}"}
    except Exception as exc:  # noqa: BLE001
        _logger.warning("skill %s failed: %s", skill_id, exc)
        return {"error": str(exc)}
```

并在 `skills_catalog.py` 增加：

```python
def resolve_skill_dir(skill_id: str) -> Path:
    return _safe_skill_dir(skill_id)
```

- [ ] **Step 5: 跑测通过**

Run: `cd backend && python -m pytest tests/test_skill_runtime.py -v`  
Expected: PASS

- [ ] **Step 6: Commit（仅用户要求时）**

```bash
git add backend/app/services/skill_runtime.py backend/app/services/skills_catalog.py backend/tests/test_skill_runtime.py
git commit -m "$(cat <<'EOF'
feat(ai): 增加 Skill Python 薄运行时

EOF
)"
```

---

### Task 2: 示范 skill + `run_skill` 工具 + catalog `runnable`

**Files:**
- Create: `backend/app/skills/market-emotion/skill.py`
- Modify: `backend/app/skills/market-emotion/SKILL.md`
- Modify: `backend/app/services/skills_catalog.py`（`list_skills` 加 `runnable`）
- Modify: `backend/app/services/ai_tools.py`
- Modify: `backend/tests/test_ai_tools_skills.py`
- Modify: `backend/tests/test_skills_catalog.py`（断言 market-emotion `runnable`）

**Interfaces:**
- `list_skills()` 每项含 `runnable: bool` = `(skills_root()/id/skill.py).is_file()`
- `_run_skill(db, user_id, args) -> Any` → `run_skill_module(skill_id, SkillContext(db, user_id), args.get("args") if nested else filtered)`
  - 参数：`skill_id` 必填；其余键作为 `args` 传给 `run`（或显式 `args` 对象；推荐：`payload = {k:v for k,v in args.items() if k != "skill_id"}`）
- `TOOL_HANDLERS["run_skill"]`；`TOOL_DEFINITIONS` 增加条目；**不**加入 `WRITE_TOOL_NAMES` / `WRITE_HANDLERS`

- [ ] **Step 1: 写失败工具测 + catalog runnable 测**

```python
# 追加 test_ai_tools_skills.py
from unittest.mock import MagicMock, patch

from app.services.ai_tools import WRITE_TOOL_NAMES, execute_tool


def test_run_skill_not_write() -> None:
    assert "run_skill" not in WRITE_TOOL_NAMES


def test_run_skill_market_emotion_mocked() -> None:
    with patch("app.services.skill_runtime.run_skill_module", return_value={"emotion": {"phase": "x"}, "overview": {}}) as m:
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "market-emotion"})
    assert "emotion" in out
    m.assert_called_once()


def test_run_skill_missing_id() -> None:
    out = execute_tool(MagicMock(), "u", "run_skill", {})
    assert "error" in out
```

```python
# test_skills_catalog.py 追加
def test_market_emotion_runnable_after_skill_py() -> None:
    skills = {s["id"]: s for s in list_skills()}
    # 实现 skill.py 后：
    assert skills["market-emotion"].get("runnable") is True
    assert skills["watchlist"].get("runnable") is False
```

（若 Step 1 在写 `skill.py` 前跑 catalog 测会红——先写工具测与 `runnable False`，再写 skill.py 后改断言；或本 task 内先实现再绿。）

- [ ] **Step 2: 示范 skill.py**

```python
# backend/app/skills/market-emotion/skill.py
from __future__ import annotations

from typing import Any

from app.services import market


def run(ctx: Any, args: dict[str, Any]) -> dict[str, Any]:
    _ = args
    emotion = market.load_emotion(ctx.db)
    overview = market.market_overview(ctx.db)
    return {
        "emotion": emotion,
        "overview": overview.model_dump() if hasattr(overview, "model_dump") else overview,
    }
```

- [ ] **Step 3: SKILL.md 补一行**

在工具表增加：

```markdown
| run_skill | skill_id=market-emotion，执行本目录 skill.py |
```

- [ ] **Step 4: catalog `runnable`**

```python
# list_skills 内 append 前
meta = _load_skill_meta(skill_id, text)
meta["runnable"] = (entry / "skill.py").is_file()
skills.append(meta)
```

- [ ] **Step 5: ai_tools 接线**

```python
def _run_skill(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.skill_runtime import SkillContext, run_skill_module

    sid = str(args.get("skill_id") or "").strip()
    if not sid:
        return {"error": "缺少 skill_id"}
    payload = {k: v for k, v in args.items() if k != "skill_id"}
    return run_skill_module(sid, SkillContext(db=db, user_id=user_id), payload)

# TOOL_HANDLERS["run_skill"] = _run_skill
# TOOL_DEFINITIONS 增加：
{
    "type": "function",
    "function": {
        "name": "run_skill",
        "description": "执行内置 skill 目录下 skill.py 的 run()（只读示范；超时约 5s）",
        "parameters": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string", "description": "如 market-emotion"},
            },
            "required": ["skill_id"],
            "additionalProperties": True,
        },
    },
}
```

同步更新 `test_ai_tools.py` 期望的工具名集合（若有硬编码列表，加入 `run_skill`）。

- [ ] **Step 6: 跑测**

Run:

```bash
cd backend && python -m pytest tests/test_skill_runtime.py tests/test_ai_tools_skills.py tests/test_skills_catalog.py tests/test_ai_tools.py -v
```

Expected: PASS

- [ ] **Step 7: Commit（仅用户要求时）**

```bash
git add backend/app/skills/market-emotion/skill.py backend/app/skills/market-emotion/SKILL.md \
  backend/app/services/skills_catalog.py backend/app/services/ai_tools.py \
  backend/tests/test_ai_tools_skills.py backend/tests/test_skills_catalog.py backend/tests/test_ai_tools.py
git commit -m "$(cat <<'EOF'
feat(ai): 接入 run_skill 与 market-emotion 示范

EOF
)"
```

---

### Task 3: 文档

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap**

Skills 行改为类似：

> 有内置 SKILL.md + list/read；薄 `run_skill`（同进程 + 超时）+ `market-emotion` 示范；仍非桌面全量 Python registry

「建议下一刀」写：其余内置 skill 补 `skill.py`；或 B 站同步 / Docker 等。

- [ ] **Step 2: smoke**

AI 相关节增加：

`- [ ] Agent / 工具：run_skill(skill_id=market-emotion) 可返回 emotion（需情绪数据或可接受空结构）`

- [ ] **Step 3: 相关测再确认**

```bash
cd backend && python -m pytest tests/test_skill_runtime.py tests/test_ai_tools_skills.py tests/test_skills_catalog.py -q
```

Expected: PASS

- [ ] **Step 4: Commit（仅用户要求时）**

```bash
git add docs/gap-vs-desktop.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 记录 Skill 薄运行时与 smoke 项

EOF
)"
```

---

## Spec coverage（自检）

| Spec | Task |
|------|------|
| skill_runtime + 超时 + 错误包装 | 1 |
| resolve 安全 / 非法 id | 1 |
| market-emotion skill.py | 2 |
| run_skill 工具、非写工具 | 2 |
| list_skills.runnable | 2 |
| gap / smoke | 3 |
| 真沙箱 / 五 skill / 桌面移植 | 非目标 |

## Placeholder scan

无 TBD；测试与实现代码已内嵌。超时中文错误文案以实现为准（测允许「超时」或 timeout）。
