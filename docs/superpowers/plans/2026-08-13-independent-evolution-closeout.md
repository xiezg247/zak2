# 独立演进 #1 收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清除 API 中引导 zak 的错误文案，划掉路线图 #1，并补 smoke 验收条。

**Architecture:** 直接替换 4 处 `HTTPException.detail`；新增小单测锁定文案；文档两文件收口；`check.sh` 验收。

**Tech Stack:** FastAPI、pytest、Markdown。

## Global Constraints

- 文案以 [spec](../specs/2026-08-13-independent-evolution-closeout-design.md) 为准
- 不抽 messages 模块；不跑 Compose 手测
- Commit 简体中文；不 push

---

### Task 1: 替换文案 + 单测

**Files:**
- Modify: `backend/app/services/engine.py`
- Modify: `backend/app/services/pattern_screen.py`
- Modify: `backend/app/services/backtest_engine.py`
- Modify: `backend/app/services/bars.py`
- Create: `backend/tests/test_zak_copy_closeout.py`

**Interfaces:**
- Consumes: `engine._require_quotes`；`pattern_screen.run_pattern_screen`；`backtest_engine.load_daily_bars`；`bars.load_bars`
- Produces: 无 zak 引导的 detail 字符串

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_zak_copy_closeout.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.screener import PatternRunRequest
from app.services import bars, engine, pattern_screen
from app.services.backtest_engine import load_daily_bars


def test_require_quotes_empty_points_to_collector() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.meta.return_value = {"quote_count": 0}
    with pytest.raises(HTTPException) as ei:
        engine._require_quotes(store)
    assert ei.value.status_code == 503
    assert "quote-collector" in ei.value.detail
    for bad in ("zak 侧", "zak 下载", "使用 zak", "collect_quotes"):
        assert bad not in ei.value.detail


def test_pattern_screen_empty_quotes_points_to_collector() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.meta.return_value = {"quote_count": 0}
    with pytest.raises(HTTPException) as ei:
        pattern_screen.run_pattern_screen(
            PatternRunRequest(pattern_id="ma_bull", top_n=5, max_scan=10),
            db=MagicMock(),
            store=store,
        )
    assert "quote-collector" in ei.value.detail
    for bad in ("zak 侧", "zak 下载", "使用 zak"):
        assert bad not in ei.value.detail


def test_load_daily_bars_insufficient_points_to_ops() -> None:
    db = MagicMock()
    db.scalars.return_value = []  # 0 bars → len < 30
    with pytest.raises(HTTPException) as ei:
        load_daily_bars(
            db,
            vt_symbol="SHSE.600519",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )
    assert ei.value.status_code == 404
    assert "Ops" in ei.value.detail
    for bad in ("zak 侧", "zak 下载", "使用 zak"):
        assert bad not in ei.value.detail


def test_load_bars_empty_points_to_ops() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    with pytest.raises(HTTPException) as ei:
        bars.load_bars(db, symbol="600519", exchange="SHSE")
    assert ei.value.status_code == 404
    assert "Ops" in ei.value.detail
    for bad in ("zak 侧", "zak 下载", "使用 zak"):
        assert bad not in ei.value.detail
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_zak_copy_closeout.py -q
```

Expected: FAIL（旧文案仍含 zak）

- [ ] **Step 3: 替换四处 detail**

`engine.py` 与 `pattern_screen.py`：

```python
raise HTTPException(
    status_code=503,
    detail="行情快照为空，请启动 quote-collector（python -m app.quote_collector）",
)
```

`backtest_engine.py`：

```python
raise HTTPException(status_code=404, detail=f"日 K 不足（{len(rows)}），请先在 Ops 补全日 K")
```

`bars.py`：

```python
raise HTTPException(status_code=404, detail="无 K 线数据，请先在 Ops 补全日 K")
```

- [ ] **Step 4: 跑测通过 + 扫漏网**

```bash
cd backend && uv run pytest tests/test_zak_copy_closeout.py tests/test_engine.py tests/test_pattern_screen.py tests/test_backtest_engine.py -q
rg -n 'zak 侧|zak 下载|使用 zak' app
```

Expected: 测试 PASS；`rg` 无匹配。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/engine.py \
  backend/app/services/pattern_screen.py \
  backend/app/services/backtest_engine.py \
  backend/app/services/bars.py \
  backend/tests/test_zak_copy_closeout.py
git commit -m "$(cat <<'EOF'
fix(copy): API 空行情/日 K 文案改指向 collector 与 Ops

去掉「zak 侧」「zak 下载」引导，收口独立演进漏网提示。
EOF
)"
```

---

### Task 2: 路线图 + smoke + check.sh

**Files:**
- Modify: `docs/product-roadmap.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: 划掉 #1**

将：

```markdown
1. 完成本独立演进落地（Compose / Alembic / `zak2:` 前缀 / 去 CLI 文案 / 导入脚本）
```

改为：

```markdown
1. ~~完成本独立演进落地~~（已完成 → [总纲](./superpowers/specs/2026-08-11-zak2-independent-evolution-design.md)；收口 → [spec](./superpowers/specs/2026-08-13-independent-evolution-closeout-design.md)）
```

- [ ] **Step 2: smoke 增条**

在「## 0. 前置」末尾或「## 4. 选股 Hub」附近增加：

```markdown
- [ ] 选股空行情 / 回测或 K 线无日 K 时的错误文案引导 quote-collector 或 Ops，不出现「zak 侧」「zak 下载」
```

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: `OK：测试与构建通过`

- [ ] **Step 4: Commit**

```bash
git add docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 划掉路线图 #1 并补充独立演进收口 smoke

文案漏网已修；标记独立演进落地完成。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 四处 detail | 1 |
| 测试锁定文案 | 1 |
| check.sh | 2 |
| 路线图 #1 | 2 |
| smoke 条 | 2 |
| 不跑 Compose 手测 | Global |

无 TBD。`load_daily_bars` 签名为 `(db, *, vt_symbol, start_date, end_date)`。
