# 投研团队编排（薄）设计

日期：2026-08-06  
状态：已批准（方案 A）

## 目标

单票财务/风险/策略规则评分 + chief LLM 汇总流式输出。对齐桌面快速团队，不做深度三 LLM。

## API

`POST /api/v1/ai/team/stream`  
body: `{ "vt_symbol": "600519.SSE", "session_id": optional }`

SSE events:
- `{type, agent, kind, ...}` agent ∈ financial|risk|strategy|chief|system
- kind: started | score | delta | done | error

## 流程

预取 → 三维规则分 → chief 一次流式 LLM → 可选写入会话消息

## 非目标

深度多 LLM、研报落库、MCP。
