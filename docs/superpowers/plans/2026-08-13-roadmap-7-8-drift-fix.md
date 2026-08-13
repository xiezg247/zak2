# 路线图 #7/#8 漂移纠偏 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 `docs/product-roadmap.md` #7/#8 摘要，去掉「恒 skipped」误导，改为「当时占位 + 现状指针」。

**Architecture:** 纯文档一行级替换；不改代码、smoke、归档 spec/plan。验收用 `rg` 确认。

**Tech Stack:** Markdown；git。

## Global Constraints

- 仅改 `docs/product-roadmap.md`
- 方案 A：历史定格 + 指针（见 [spec](../specs/2026-08-13-roadmap-7-8-drift-fix-design.md)）
- #7/#8 仍分别链接 batch3 / batch4 原 spec
- 正文不得再出现「恒 skipped」
- Commit message 简体中文；不 push

---

### Task 1: 改写路线图 #7/#8

**Files:**
- Modify: `docs/product-roadmap.md`（近期待办第 7、8 条）

**Interfaces:**
- Consumes: 无
- Produces: #7/#8 新摘要文案（供人工/rg 验收）

- [ ] **Step 1: 替换 #7/#8**

将：

```markdown
7. ~~Ops planned 第三批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch3-design.md)）：`warm_watchlist_strategy_cache` / `scan_horizon_outlook` 为可跑占位（恒 skipped）
8. ~~Ops planned 第四批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch4-design.md)）：`prefetch_concept_board` / `fill_focus_pool_minute` 可跑占位（恒 skipped）；catalog 已无 planned
```

改为：

```markdown
7. ~~Ops planned 第三批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch3-design.md)）：`warm_watchlist_strategy_cache` / `scan_horizon_outlook` 当时注册为可跑占位；现状见 #26 / #29（展望/策略启发式）
8. ~~Ops planned 第四批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch4-design.md)）：`prefetch_concept_board` / `fill_focus_pool_minute` 当时注册为可跑占位（catalog 已无 planned）；现状见 #27 / #30
```

- [ ] **Step 2: 验收**

```bash
rg -n "恒 skipped" docs/product-roadmap.md
# Expected: 无输出（exit 1 / no matches）

rg -n "当时注册为可跑占位|现状见 #26|#29|#27|#30" docs/product-roadmap.md
# Expected: 两行分别命中 #7/#8

rg -n "ops-planned-batch3-design|ops-planned-batch4-design" docs/product-roadmap.md
# Expected: 仍各有一条链接
```

- [ ] **Step 3: Commit**

```bash
git add docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs(roadmap): 纠偏 #7/#8 恒 skipped 漂移

保留第三/四批占位里程碑，指针到 #26–30 现状。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 仅改 product-roadmap #7/#8 | 1 |
| 去掉「恒 skipped」 | 1 Step 2 |
| 仍链 batch3/4 | 1 Step 2 |
| 「当时占位」+「现状见」 | 1 Step 1 |
| 不改 smoke/归档/代码 | Global Constraints |

无 TBD。

---

# Roadmap drift SDD progress

- Task 1: done @ 3f0a114 (approved)
- Final review: APPROVED (docs-only, task review sufficient)
