# AI 写操作确认卡 Implementation Plan

> **For agentic workers:** 按任务顺序实现；每任务自测后再进入下一任务。

**Goal:** Agent 可提议加自选/写备忘，UI 确认后才写库。

**Architecture:** 写工具挂起为 proposal → SSE `confirm_required` → confirm/reject API 执行或取消。

**Tech Stack:** FastAPI、现有 ai_agent/ai_tools、Vue AiView、pytest

## 文件

| 文件 | 职责 |
|------|------|
| `backend/app/services/ai_proposals.py` | proposal 存储/确认/拒绝 |
| `backend/app/services/ai_tools.py` | 注册写工具 + 执行体 |
| `backend/app/services/ai_agent.py` | 写工具改走 proposal |
| `backend/app/api/v1/ai.py` | confirm/reject 路由 |
| `frontend/src/api/ai.ts` + `AiView.vue` | 确认卡 UI |
| `backend/tests/test_ai_proposals.py` 等 | 单测 |
| `docs/gap-vs-desktop.md` | 缺口更新 |

## 任务

1. proposal 服务 + 单测  
2. 写工具定义与 handlers；agent 拦截  
3. API + 前端确认卡  
4. 全量 pytest + npm build；更新缺口表  
