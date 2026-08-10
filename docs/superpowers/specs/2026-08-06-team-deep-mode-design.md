# 投研团队深度模式设计

日期：2026-08-06  
状态：已批准（方案 1；API 用 mode；三分析师并行流式）

## 目标

在现有快速团队编排上增加 `mode=deep`：预取 + 规则分保留，财务/风险/策略三路 **并行 LLM 流式**，再由首席汇总。仅改 zak2。

## API

`POST /api/v1/ai/team/stream`

```json
{
  "vt_symbol": "600519.SSE",
  "session_id": null,
  "mode": "fast"
}
```

- `mode`: `"fast"` | `"deep"`，默认 `"fast"`（行为与现网一致）
- SSE 事件形状不变：`{type, agent, kind, ...}`  
  `agent` ∈ financial|risk|strategy|chief|system  
  `kind` ∈ started|score|delta|done|error  
- 深度模式额外：子 Agent 在 `score` 之后可有 `delta`（LLM 正文）；快速模式子 Agent 仍仅 `score`（无 LLM delta）

## 流程（deep）

1. `system/started`
2. 预取（复用 `prefetch_team`）
3. 三维规则分 `score` + `weighted`（与 fast 相同）
4. 三 Agent **并行** `stream_completion`，SSE 按完成块交错推送对应 `agent` 的 `delta`
5. 三路 `done` 齐后 → `chief` 流式（输入 = 预取摘要 + 规则分 + 三路全文）
6. `system/done`（含完整报告文本，可选写入 session）

## 提示词边界

- 财务 / 风险 / 策略：各限定本维，基于预取 JSON，禁止编造未出现指标，禁止具体买卖点位
- 首席：综合三路与情绪阶段，Markdown，≤800 字，同样禁止点位/收益保证

## 失败与降级

- 某子 Agent LLM 失败 → 该维用规则 `summary`（及 highlights）作为正文兜底，不中断整场
- 首席失败 → 整篇规则兜底报告（复用现有 `_fallback_report`，可附三路正文摘要）
- 未配置 LLM：深度等价于「规则分 + 三路规则正文 + 规则首席」，仍可跑通

## 并发实现要点

- 用线程池或等效方式并行消费三路 `stream_completion` iterator
- 经队列合并为单生成器，保证 SSE 单连接有序写出
- 不在请求内做跨用户共享线程池（进程内短生命周期即可）

## 前端

- AI 页团队区：`mode` 开关（快速 / 深度），默认快速
- 深度时按钮可提示更慢/耗 token
- 展示三维流式正文 + 首席；规则分卡片保留

## 非目标

- ReAct / 多轮 tool calling / MCP
- 研报落库（`stock_analysis_reports`）与 `zak://` 链接
- 修改 zak 桌面代码
- 深度取代快速

## 测试

- `mode=fast` 回归：无子 Agent `delta`（或行为与现网一致）
- `mode=deep`：mock 三路 + 首席流式，断言并行路径下四类 agent 均有 `delta`/`done`
- 子 Agent 失败兜底：一场中仍有 `system/done`
