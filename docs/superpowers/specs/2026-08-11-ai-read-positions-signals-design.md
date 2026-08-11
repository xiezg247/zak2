# AI 只读：持仓 / 信号名单 / 风控 + positions Skill 设计

日期：2026-08-11  
状态：已批准（方案 A：三独立只读工具 + `positions` Skill 聚合）  
范围：仅 zak2；不改 zak / vnpy-*；不改 REST / 确认卡 / 写工具语义

## 背景

写工具已具备：`upsert_position` / `delete_position` / `add_signal_panel` / `remove_signal_panel`。  
Web REST 已有持仓、信号名单、`trading-risk` 偏好；策略看盘含 `risk_summary`（仓位占比、计划外等）。  
Agent **缺只读工具**，无法在对话中先查再写；`run_skill` 亦无对应 skill。

产品路线候选：AI 只读持仓/信号工具。本刀落地三工具 + Skill。

## 目标

1. Agent 可只读查询：**持仓列表**、**信号名单**、**风控偏好 + risk_summary**。  
2. 新增薄 Skill `positions`，支持 `run_skill` 总览或按 `section` 分流。  
3. 复用现有 repo / strategy_board 计算，与 Web 语义一致。

## 非目标

- 改写工具 / 确认卡 / proposal  
- 改 REST API 契约  
- 计划激活/编辑 UI  
- 下单、MCP 写操作、桌面 skill registry  
- 把完整 `strategy_board`（信号 cache 明细）塞进本刀（仅取 risk_summary 所需字段）

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：三独立工具 + Skill 聚合 |
| 实现落点 | `ai_read_tools.py` + `ai_tools` definitions/dispatch |
| Skill id | `positions` |
| 风控内容 | prefs + `risk_summary`（与自选策略看盘同源） |
| 持仓行情 | 可选 `with_quotes`（默认 true，对齐 `get_watchlist`） |

---

## 1. 只读工具

全部 **不在** `WRITE_TOOL_NAMES`；经 `execute_tool` 立即返回。

| 工具 | 参数 | 返回要点 |
|------|------|----------|
| `get_positions` | `limit`（默认 20，夹逼 1–20）；`with_quotes`（默认 true） | `{ count, items[] }`：vt_symbol、成本、数量、买入日、notes、plan_pct 等；可选 last_price/change_pct |
| `get_signal_panel` | 无必填 | `signal_panel_repo.panel_payload`：`symbols` / `count` / `max_symbols` |
| `get_trading_risk` | 无必填（可选 `config_key`，透传策略看盘缺省逻辑） | `{ prefs, risk_summary }`：prefs 来自 `trading_risk.load_trading_risk_prefs`；`risk_summary` 来自 `strategy_board.load_strategy_board(...).risk_summary`（或抽出只算 summary 的薄封装，避免多余大字段进 LLM） |

### `get_trading_risk` 细节

- **prefs**：`total_capital`、`stop_loss_pct`、`caution_float_pct`、`realized_pnl_today`  
- **risk_summary**（与 Web 一致）：`actual_position_pct`、`plan_max_pct`、`off_plan_count`、`off_plan_symbols`、`active_plan_date`、`plan_symbols`（可截断：仅保留 vt_symbol + status，避免过长）  
- 实现优先：调用现有 `load_strategy_board` 后只取 `risk_summary` + 另取 prefs；若板过大再抽 helper，**本刀允许先整板取 summary**，测试断言字段存在即可。

### 边界

- 空持仓 / 空信号名单 → 正常返回 count=0，不 error  
- Redis 行情失败 → 仍返回持仓，quotes 字段省略（对齐 `get_watchlist`）  
- repo / HTTPException → `{ error: detail }`（与其它只读工具一致，若现有只读未统一则跟 `get_stock_notes` 风格）

---

## 2. Skill `positions`

路径：

- `backend/app/skills/positions/SKILL.md`  
- `backend/app/skills/positions/skill.py`

行为（对齐 `notes`）：

| `section` / 参数 | 行为 |
|------------------|------|
| 缺省或 `section=all` | 一次返回 `{ positions, signal_panel, trading_risk }`（各调对应 read helper） |
| `section=positions` | 仅 `get_positions` |
| `section=signals` | 仅 `get_signal_panel` |
| `section=risk` | 仅 `get_trading_risk` |

`SKILL.md` 写明：读用本 skill / 三工具；写仍用确认卡写工具（upsert/delete/add/remove）。

自动被 `skills_catalog` 目录扫描收录（与现有 skill 相同，无额外注册表）。

---

## 3. 模块与测试

| 路径 | 职责 |
|------|------|
| `backend/app/services/ai_read_tools.py` | 新增三个函数 |
| `backend/app/services/ai_tools.py` | definitions + dispatch 到 read helpers；**不**加入 WRITE |
| `backend/app/skills/positions/*` | Skill 文档 + run |
| `backend/tests/test_ai_read_tools.py` | mock：positions / panel / risk；run_skill positions |
| `backend/tests/test_ai_tools.py` / skills catalog 相关 | 断言新工具在 definitions、不在 WRITE；catalog 含 `positions` |
| `docs/product-roadmap.md` | 候选「AI 只读持仓/信号」标为已完成并链本 spec |
| `docs/smoke-checklist.md` | Agent 可 `get_positions` / `get_signal_panel` / `get_trading_risk`；`run_skill` positions |

---

## 4. 验收

1. `pytest`：read helpers + definitions/WRITE 集合 + `run_skill` positions（mock）通过。  
2. 手动（可选）：登录后 AI 问「我有哪些持仓 / 信号名单 / 仓位占比」，工具被调用且返回合理。  
3. 写路径回归：持仓/信号确认卡行为不变。

## 明确不做（复述）

双写桌面、zak CLI、下单、计划激活编辑。
