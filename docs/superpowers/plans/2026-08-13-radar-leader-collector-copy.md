# 雷达/龙头空行情文案去 collect_quotes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将雷达涨幅榜与龙头合成空行情文案改为短版引导 `quote-collector`。

**Architecture:** 直接替换两处字符串；新增小单测；`rg` + `check.sh` 验收。

**Tech Stack:** pytest、FastAPI services。

## Global Constraints

- 文案固定：`行情快照为空，请启动 quote-collector`
- 不改 `ops_catalog` job_id `collect_quotes`
- 不改 engine/pattern 长文案
- Commit 简体中文；不 push

---

### Task 1: 替换 + 单测 + check.sh

**Files:**
- Modify: `backend/app/services/radar.py`
- Modify: `backend/app/services/leader_screen.py`
- Create: `backend/tests/test_radar_leader_collector_copy.py`

**Interfaces:**
- Consumes: `radar._synth_change_top`；`leader_screen.synth_leader_pick_rows`
- Produces: empty_message 短文案

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_radar_leader_collector_copy.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import leader_screen, radar


def test_synth_change_top_empty_points_to_collector() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.list_rank.return_value = []
    with patch.object(radar, "get_quote_store", return_value=store):
        card = radar._synth_change_top()
    assert "quote-collector" in (card.empty_message or "")
    assert "collect_quotes" not in (card.empty_message or "")


def test_synth_leader_pick_empty_points_to_collector() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.meta.return_value = {"quote_count": 0}
    with patch.object(leader_screen, "get_quote_store", return_value=store):
        rows, _sub, empty = leader_screen.synth_leader_pick_rows(MagicMock(), top_n=5)
    assert rows == []
    assert "quote-collector" in empty
    assert "collect_quotes" not in empty
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_radar_leader_collector_copy.py -q
```

Expected: FAIL（仍含 collect_quotes）

- [ ] **Step 3: 替换两处**

`radar.py` `_synth_change_top`：

```python
empty_message="行情快照为空，请启动 quote-collector",
```

`leader_screen.py` `synth_leader_pick_rows`：

```python
return [], "", "行情快照为空，请启动 quote-collector"
```

- [ ] **Step 4: 跑测 + 扫漏网**

```bash
cd backend && uv run pytest tests/test_radar_leader_collector_copy.py -q
rg -n '请先 collect_quotes' app
```

Expected: PASS；`rg` 无匹配（`ops_catalog` job_id 不含「请先」前缀，应仍为 0）。

- [ ] **Step 5: check.sh**

```bash
./scripts/check.sh
```

Expected: `OK：测试与构建通过`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/radar.py \
  backend/app/services/leader_screen.py \
  backend/tests/test_radar_leader_collector_copy.py
git commit -m "$(cat <<'EOF'
fix(copy): 雷达/龙头空行情改引导 quote-collector

去掉「请先 collect_quotes」用户文案。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| radar / leader 两处替换 | 1 |
| 短文案 | 1 |
| 单测 + 无「请先 collect_quotes」 | 1 |
| 不改 job_id | Global |

无 TBD。
