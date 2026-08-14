# 雷达展望行动化设计

日期：2026-08-14  
状态：已批准
范围：仅 zak2；展望/预测表行级入自选与入草案；不做 AI / 批量  
前置：雷达展望加深（#52）；交易计划生命周期（#42）

## 背景

#52 在雷达页提供共振展望与规则预测双区只读表。卡片详情已有入自选；工具栏有「生成次日计划草案」（共振 TopN **覆盖**式写入 draft）。展望/预测**行**尚无操作，用户需手抄代码。

产品选择：两表行级「自选」「草案」；草案走专用 **append** API（无 draft 则建空稿再追加），与工具栏全量生成并存。

## 目标

1. `POST /api/v1/playbook/plans/draft-append`：确保次一交易日 draft → 追加一标的（幂等 / 上限 20）。  
2. 共振展望表、规则预测表操作列：「自选」「草案」。  
3. 入自选复用现有 watchlist API。  
4. 路线图 #56 + smoke；`./scripts/check.sh` 绿。

## 非目标

- 多选批量入自选/草案  
- AI 读 predict / LLM 短评  
- 用户共振权重进 job  
- 改工具栏「生成次日计划草案」覆盖语义  
- 交易下单、改 CTA  
- 改卡片详情既有按钮（可复用 `addWatchTo` 实现）

## 决策摘要

| 项 | 选择 |
|----|------|
| 行操作 | 自选 + 草案（两表） |
| 无 draft | 自动建空 draft 再追加 |
| trade_date | 与生成草案相同：`resolve_next_trade_date` |
| 冰点/退潮 | append **不**因情绪拒建空稿（与全量生成不同） |
| 批量 | 不做 |
| API | 专用 `draft-append`，非前端 list+PATCH |

---

## 1. API

### `POST /api/v1/playbook/plans/draft-append`

**Request**

```json
{ "vt_symbol": "600519.SSE", "name": "贵州茅台", "source": "horizon" }
```

- `vt_symbol` 必填  
- `name`、`source`（`horizon` \| `predict`）可选  

**服务**（建议 `plan_draft.append_symbol_to_draft`）：

1. 解析 vt；非法 → 400  
2. `td, _ = resolve_next_trade_date(db)`  
3. 查找用户该日 `status=draft`；无则新建：  
   - `notes` 默认「展望行追加」  
   - `max_position_pct` 用既有默认（如 0.3）  
   - `emotion_expected` 可空或写入当前 stage（不因此拒建）  
4. 已含该 vt → 200，`{ added: false, plan_id, trade_date, symbol_count, message }`  
5. `symbol_count >= MAX_PLAN_SYMBOLS(20)` → 400  
6. 否则插入 `TradingPlanSymbol` → 200，`{ added: true, ... }`  

可选：`entry_conditions` 写入来源标记（如「来自规则预测」），非必须。

入自选：现有 `POST` watchlist add，无新接口。

---

## 2. UI（RadarView）

| 控件 | 行为 |
|------|------|
| 展望表 / 预测表 | 列「操作」：按钮「自选」「草案」 |
| 自选 | `addWatchTo(vt, name, rowMsg)`；短反馈 |
| 草案 | 调 `draft-append`；成功提示 + 链 `/playbook`；已在/满员可读文案 |
| 防连点 | 复用 `actingVt` |

工具栏「生成次日计划草案」不变。

---

## 3. 模块边界

| 路径 | 变更 |
|------|------|
| `backend/app/services/plan_draft.py` | `append_symbol_to_draft` |
| `backend/app/schemas/content.py`（或邻近） | In/Out |
| `backend/app/api/v1/content.py` | 路由 |
| `backend/tests/test_plan_draft.py`（或新测） | 新建/追加/幂等/上限 |
| `frontend/src/api/content.ts` | `draftAppend` |
| `frontend/src/views/RadarView.vue` | 两表操作列 |
| docs | #56、smoke、本 spec |

---

## 4. 验收

- [ ] 两表可见「自选」「草案」  
- [ ] 无 draft 时草案可成功并建空稿  
- [ ] 重复追加 `added=false`；满 20 有明确错误  
- [ ] 自选成功/已在失败文案可读  
- [ ] 工具栏生成草案仍可用  
- [ ] `./scripts/check.sh` 绿  
- [ ] 路线图 #56 + smoke  

## 风险

| 风险 | 缓解 |
|------|------|
| 与全量生成互相覆盖 | 文案区分；append 不删既有标的；全量生成仍清空重写（既有行为） |
| trade_date 误解为「今天」 | notes/UI 沿用「次日计划」语义 |
| 冰点仍可追加 | 产品明确；全量生成仍拦冰点 |

## 后续刀

- 批量勾选  
- AI 读 predict  
- 用户权重进展望 job
