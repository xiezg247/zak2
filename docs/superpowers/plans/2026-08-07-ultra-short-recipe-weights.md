# 超短配方权重可编辑 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 将 `ultra_short_unified` 纳入现有 recipe_weights 可编辑体系。

**Architecture:** 扩 `EDITABLE_RECIPES` / 默认表 / scorer 签名 / Hub `WEIGHT_EDITABLE`；API 路径已通。

**Tech Stack:** 现有 recipe_weights + engine + ScreenerHubView。

**Spec:** `docs/superpowers/specs/2026-08-07-ultra-short-recipe-weights-design.md`

## Global Constraints

- 只改 zak2；复用归一化与 meta 存储
- 默认 board/momentum/turnover = 0.4/0.35/0.25
- Commit 仅用户明确要求时（默认跳过）

---

## File map

| 文件 | 改动 |
|------|------|
| `backend/app/services/recipe_weights.py` | EDITABLE + DEFAULT + LABELS |
| `backend/app/services/engine.py` | `_score_ultra_short(..., weights=None)` 并在 EDITABLE 分支传 weights |
| `backend/tests/test_recipe_weights.py` | 超短用例 |
| `frontend/src/views/ScreenerHubView.vue` | `WEIGHT_EDITABLE` |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 一行 |

---

### Task 1: 后端 + 测

**Files:** recipe_weights.py, engine.py, test_recipe_weights.py

- [ ] **Step 1:** 断言 `EDITABLE` 含 ultra；normalize 默认和为 1；GET API 200（可扩现有 fixture）

- [ ] **Step 2:** 实现 DEFAULT/LABELS；`_score_ultra_short` 接受 weights：

```python
def _score_ultra_short(row, weights=None):
    w = weights or recipe_weights_svc.DEFAULT_WEIGHTS["ultra_short_unified"]
    board = max(0.0, min(row.limit_times / 3.0, 1.0))
    momentum = max(0.0, min(row.change_pct / 10.0, 1.0))
    turnover = max(0.0, min(row.turnover_rate / 20.0, 1.0))
    return w.get("board", 0.4) * board + w.get("momentum", 0.35) * momentum + w.get("turnover", 0.25) * turnover
```

确认 `run_recipe_screen` 对 EDITABLE 调 scorer 时传入 `weights`（盘中盘后已有则超短自动覆盖）。

- [ ] **Step 3:** 单测权重翻转排序（两只 mock QuoteRow limit_times 不同）

- [ ] **Step 4:** pytest 相关文件 PASS；Commit 跳过

---

### Task 2: 前端 + 文档 + 全量

**Files:** ScreenerHubView.vue, gap, smoke

- [ ] `WEIGHT_EDITABLE` 加 `'ultra_short_unified'`
- [ ] gap/smoke 注明超短可调权重
- [ ] `pytest` 全量 + `npm run build`；Commit 跳过

---

## Spec coverage

| Spec | Task |
|------|------|
| defaults + scorer + tests | 1 |
| Hub + docs | 2 |

无 TBD。
