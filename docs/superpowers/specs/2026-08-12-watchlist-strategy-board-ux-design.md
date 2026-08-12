# 自选策略看盘 UX 闭环设计

日期：2026-08-12  
状态：已批准（方案 A：note/空态文案去桌面依赖 + 前端 tip 对齐；不接引擎）  
范围：仅 zak2 策略看盘文案与空态；不做策略引擎 / 预热写 cache

## 背景

自选页策略看盘（信号区、持仓区、风控、计划、通知）已可用。`load_strategy_board` 的 `note` 与前端空态仍引导「zak 桌面刷新」，与独立演进定位不符。`warm_watchlist_strategy_cache` 仍为恒 skipped（无引擎），本刀不实现预热。

## 目标

1. 后端三条 `note` 改为 zak2 语义：编辑信号名单 / 确认 Redis·PG cache / 说明尚无策略引擎预热。  
2. 前端信号空行、名单 tip、持仓 tip 同步，去掉桌面导向。  
3. 布局保持双栏 `strategy-grid`；不改风控/计划/通知/持仓 CRUD 逻辑。  
4. 单测覆盖 `note` 分支，断言不含「桌面」。

## 非目标

- 实现策略引擎或把 `warm_watchlist_strategy_cache` 做实  
- config_key UI 选择器  
- 下单、大改 WatchlistView 结构拆分  
- 分组 / 列表排序过滤（已完成）

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：后端 note + 前端空态/tip |
| 布局 | 保持双栏，不新增大改 CSS |
| 预热 | 仅文案说明「尚未接入」，不写 cache |

---

## 1. 后端 `note`

文件：`backend/app/services/strategy_board.py`（`load_strategy_board` 末尾）

| 条件 | 文案 |
|------|------|
| `panel_symbols` 非空且 `signals` 空 | `信号名单 {N} 只，暂无策略 cache（可编辑名单，或确认 Redis/PG 已有信号缓存）。` |
| `signals` 与 `positions` 皆空 | `暂无策略缓存。zak2 尚未接入策略引擎预热；可先维护信号名单与持仓记账，或确认 Redis/PG cache 已写入。` |
| `signals` 空且有 `positions` | `持仓来自记账表；信号 cache 为空（可编辑名单，或确认 cache 已写入）。` |

条件顺序保持现有分支逻辑不变，仅替换字符串。

## 2. 前端文案

文件：`frontend/src/views/WatchlistView.vue`

| 位置 | 文案 |
|------|------|
| 信号表空行 | `无信号（可先编辑名单，或确认策略 cache 已写入）` |
| 名单 tip | `名单为空时回退「自选 ∩ 策略 cache」；上限 {panelMax} 只（存 PG）。` |
| 持仓 tip | `须先加入自选；数量 100 股整手；写入持仓记账表。` |

其它「与桌面同表 trading/risk」等风控区文案：**本刀不改**（仅策略看盘信号/持仓区）。

## 3. 测试

文件：`backend/tests/test_strategy_board.py`

- 更新 `test_load_strategy_board_empty`：断言新空态 `note`，且 `「桌面」 not in note`。  
- 增补（或参数化）覆盖：有名单无信号、有持仓无信号 的 `note` 断言（同样禁止「桌面」）。

## 4. 文档

- `docs/smoke-checklist.md`：策略看盘空态可读、不引导桌面。  
- `docs/product-roadmap.md`：近期待办记「策略看盘 UX 闭环」完成。

## 5. 验收

1. 空看板 / 有名单无信号 / 有持仓无信号 的 `note` 均无「zak 桌面」「桌面刷新」。  
2. 前端信号空行与 tip 与 §2 表一致。  
3. 持仓/信号/风控 CRUD 与刷新行为不变。  
4. 相关 pytest 通过；`./scripts/check.sh` 绿。

## 明确不做

策略引擎；Ops 预热写 cache；config_key 选择器；WatchlistView 组件拆分；风控卡片桌面同表文案（另刀）。
