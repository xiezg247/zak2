# 投研团队深度模式 Implementation Plan

> **For agentic workers:** 按任务顺序实现；每任务后跑相关 pytest。

**Goal:** `POST /ai/team/stream` 支持 `mode=deep`：规则分保留 + 三分析师并行 LLM 流式 + 首席汇总。

**Architecture:** 复用 `prefetch_team` / `compute_team_scores`；deep 用线程池 + `queue` 合并三路 `stream_completion`；fast 保持现网行为。

**Tech Stack:** FastAPI SSE、现有 `llm.stream_completion`、Vue AiView。

## Global Constraints

- 只改 zak2；不做 ReAct/研报落库
- `mode` 默认 `fast`
- 子 Agent LLM 失败用规则 summary 兜底

## Files

- `backend/app/schemas/chat.py` — `mode` 字段
- `backend/app/services/team_orchestrator.py` — fast/deep 分支与并行
- `backend/app/api/v1/ai.py` — 传入 mode
- `backend/tests/test_team_orchestrator.py` — deep 用例
- `frontend/src/api/ai.ts` / `views/AiView.vue` — 开关与三维正文
- `docs/gap-vs-desktop.md` / `smoke-checklist.md` — 勾选文案

## Tasks

- [ ] Task 1: schema + orchestrator deep 并行 + 测试
- [ ] Task 2: API 传 mode + 前端开关
- [ ] Task 3: pytest 全量 + frontend build + 文档
