# 交易计划生命周期闭环设计

日期：2026-08-13  
状态：已批准（方案 1：Playbook 就地扩展；状态流转 + 轻编辑）  
范围：仅 zak2；不改 zak；无下单；不新建独立 `/plans` 页

## 背景

雷达可写次日 `trading_plans` **draft**（`POST /radar/plan-draft`）；守则 `/playbook` 只读列表；自选「计划外」只认当日最新 **active**。中间缺激活/废弃/编辑，计划外常空转。

## 目标

1. 在守则完成计划 **激活 / 废弃 / 轻编辑**（仓位上限、备注、增删标的）。  
2. 同用户同日激活替换：旧 active → abandoned，目标 → active。  
3. `draft` 与 `active` 均可编辑；`abandoned` 只读。  
4. 打通自选 off_plan；更新 smoke 与路线图。

## 非目标

- 自选页快捷激活入口  
- 手工新建整单计划（仍依赖雷达草案或既有行）  
- 下单、桌面双写、改 `plan_draft`「只覆盖 draft」语义  
- 通知投递、AI 写计划工具（另刀）

## 决策摘要

| 项 | 选择 |
|----|------|
| 入口 | 守则 `/playbook` 计划区 |
| 范围 | 状态流转 + 轻编辑（非仅激活） |
| 同日冲突 | 激活时替换：旧 active → abandoned |
| 编辑权限 | draft 与 active 可改；abandoned 只读 |
| 架构 | Playbook 就地扩展（非独立页） |
| 状态字 | `draft` \| `active` \| `abandoned` |

---

## 1. 状态机

| 动作 | 规则 |
|------|------|
| 激活 | 目标须为 `draft` 或 `abandoned` → `active`；同 `user_id`+`trade_date` 已有其它 `active` → 先置 `abandoned`，再激活目标 |
| 废弃 | `draft`/`active` → `abandoned`；已是 `abandoned` → 幂等 200 |
| 编辑 | 仅 `draft`/`active`；`abandoned` → 403 |
| 雷达再生成 draft | 仍只 upsert 同日 **draft**，不修改任何 `active`（现有 `plan_draft` 行为保留） |

`off_plan` 算法不变：仍取该日最新一条 `status=active` 的标的集。

---

## 2. API

均需登录；挂载 `backend/app/api/v1/content.py`（`/playbook/...`）。

### 2.1 保持

`GET /api/v1/playbook/plans` → `list[PlanOut]`（可含 abandoned；默认 limit 20）。

### 2.2 新增

| 方法 | 路径 | 说明 |
|------|------|------|
| `PATCH` | `/playbook/plans/{id}` | 轻编辑 |
| `POST` | `/playbook/plans/{id}/activate` | 激活（含同日替换） |
| `POST` | `/playbook/plans/{id}/abandon` | 废弃 |

**PATCH body**（字段均可选；至少一项）：

| 字段 | 规则 |
|------|------|
| `notes` | string，可空 |
| `max_position_pct` | float，按 0–1 存储；若 `>1` 视为百分数 `/100`；夹逼 (0, 1] |
| `symbols` | 若 **省略** 该字段 → 不改标的；若 **出现** → 整表替换（空数组=清空）；元素为 vt 或灵活代码（`parse_flexible_symbol`）；上限 20；去重保序 |

非法代码 → 400 中文。成功均返回完整 `PlanOut`。

归属校验：计划 `user_id` 须为当前用户，否则 404。

### 2.3 服务层

新建 `backend/app/services/plan_manage.py`：

- `update_plan(db, user_id, plan_id, ...)`  
- `activate_plan(db, user_id, plan_id)`  
- `abandon_plan(db, user_id, plan_id)`  

复用 `PlanOut` 组装逻辑（可从 `feed.list_plans` 抽 `_plan_to_out` 或同文件私有函数，避免双份）。不改 `off_plan.py` / `strategy_board` 算法。

---

## 3. 前端（PlaybookView）

### 3.1 列表

- 展示日期、状态徽章、仓位上限%、备注、标的 chips。  
- **draft**：激活 · 废弃 · 编辑  
- **active**：废弃 · 编辑；视觉强调；旁注「自选计划外以此为准」  
- **abandoned**：无写按钮；默认收入「历史」折叠；主列表优先 draft+active（最多约 5 条主区 + 历史展开）

### 3.2 编辑态

就地表单：仓位上限（UI 用 %）、备注、标的（输入加码 → chip；chip 可删）→ 保存 / 取消。保存调 PATCH。

### 3.3 反馈

成功短文案；失败展示后端 `detail`。可选：激活成功提示「已激活，回自选可看计划外」。

### 3.4 API 客户端

`frontend/src/api/content.ts` 增加 `patchPlan` / `activatePlan` / `abandonPlan`。

雷达「去守则看计划」链接不变；本刀不改自选页。

---

## 4. 测试

### 后端

- 激活 draft → active；同日再激活另一 draft → 旧 active 为 abandoned  
- 废弃 active/draft；abandoned 再废弃幂等  
- PATCH notes / max_position_pct / symbols；abandoned → 403  
- 雷达再写 draft 不改同日 active（既有 `test_plan_draft` 回归）  
- 激活后 off_plan：持仓不在名单 → 计划外；无 active → 无计划外  

### 前端 / 工程

- Playbook 按钮可见性符合状态  
- `./scripts/check.sh` 绿  

### 文档

- `docs/product-roadmap.md` 增完成项并链本 spec  
- `docs/smoke-checklist.md`：守则激活计划 → 自选可见计划外  

## 验收

- [ ] 雷达写 draft → 守则可见 → 激活 → 自选 off_plan 生效  
- [ ] 同日第二条 draft 激活会废弃旧 active  
- [ ] active 可改标的后 off_plan 随刷新变化  
- [ ] abandoned 不可 PATCH  
- [ ] pytest + 前端 build 绿  

## 风险

- 同日多 draft 历史行：激活替换只处理 **active**；其它 draft 保留（可手动废弃）  
- `max_position_pct` UI/% 与存储 0–1：与 trading-risk 约定一致，防脏数据 `>1` 时 `/100`  
- 标的整表替换：前端须提交完整列表，避免只 PATCH notes 时误传空 `symbols`
