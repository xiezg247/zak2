# AI 写操作确认卡设计

日期：2026-08-06  
状态：已批准（方案 1 / UI 确认卡）

## 目标

在 zak2 AI Agent 中增加写操作工具（加自选、写股票备忘），**必须经前端确认卡**后才落库。

## 范围

| 工具 | 行为 |
|------|------|
| `add_watchlist` | 调用 `watchlist_repo.add_item` |
| `upsert_note_memo` | 调用 `notes.upsert_memo` |

非目标：删自选、持仓录入、信号名单、MCP。

## 流程

1. 模型调用写工具 → 服务端创建 proposal（绑定 `user_id`，TTL 10min），**不写库**
2. SSE 推送 `confirm_required`
3. tool 结果回模型：`awaiting_confirm`，提示用户点确认
4. 用户确认 → `POST /ai/proposals/{id}/confirm` 写库
5. 用户拒绝 → `POST /ai/proposals/{id}/reject`
6. 前端卡状态更新；旁注成功/取消（可不二次调 LLM）

## 安全

- proposal 校验归属；一次性；过期失效
- 写工具不走 agent 静默 `execute_tool` 成功路径

## 存储

进程内 dict + TTL（单 worker 足够；多 worker 后再迁 Redis）。
