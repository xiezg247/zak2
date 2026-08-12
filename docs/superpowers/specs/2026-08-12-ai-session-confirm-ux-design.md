# AI 会话过滤与确认卡 UX 设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端；不改 AI / 确认 API）  
范围：仅 zak2 `AiView`；不改流式协议、团队分析逻辑、消息 Markdown

## 背景

AI 页已有会话列表、流式对话、写操作确认卡、投研团队。痛点：会话不可过滤；无会话/未配置 LLM 提示弱；确认卡未展示 `args`，处理中仅 disabled。

## 目标

1. 会话列表：按标题过滤；无会话 / 无匹配空态。  
2. 未配置 LLM 时页顶明确提示。  
3. 确认卡：summary 为主；`args` 默认可折叠；处理中按钮文案。

## 非目标

- 改 `/api/v1/ai/*` 或确认/拒绝契约  
- 团队分析 UI 大改、消息 Markdown/代码高亮  
- 会话重命名、归档、多选删除

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 |
| 会话管道 | `sessions` → filter(title) → `displayedSessions` |
| args 展示 | 默认折叠；展开为格式化 JSON 或键值 |
| 未配置提示 | 文案 only，不链外文档 |

---

## 1. UI 行为

### 1.1 会话过滤

- 有 `sessions.length` 时显示输入框（placeholder「过滤会话」）。  
- `query` trim 后匹配 `title`（空标题视为「未命名」一并匹配，忽略大小写）。  
- 列表 `v-for="displayedSessions"`。

### 1.2 会话空态

| 条件 | 展示 |
|------|------|
| `!sessions.length` | 「暂无会话，点上方新对话」 |
| `sessions.length && !displayedSessions.length` | 「无匹配会话」；过滤框仍可见 |

### 1.3 未配置 LLM

- 当 `status && !status.configured`：页顶（error 旁或之上）提示：  
  `未配置 LLM_API_KEY，对话与团队分析不可用。`  
- 不禁用「新对话」按钮（创建会话仍可）；发送/团队失败路径保持现有 error。

### 1.4 确认卡

- 结构：头（待确认 + tool）→ summary → 可选「参数」折叠 → detail/error → 操作按钮。  
- `Object.keys(args || {}).length` 时显示折叠按钮；默认收起；展开内容：

```text
JSON.stringify(args, null, 2)
```

（`<pre class="args-pre">`）

- `actingId === proposal_id` 时：确认按钮文案「处理中…」，两按钮 disabled（与现网一致并补文案）。

### 1.5 不变

- `newSession` / `selectSession` / `send` / `stream` / `runTeam` / confirm/reject API 调用  
- 右侧对话空态文案可保留；与会话侧空态分开

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/AiView.vue` | 过滤、空态、确认卡分层、样式 |
| `docs/smoke-checklist.md` | `/ai` 检查项 |
| `docs/product-roadmap.md` | 近期待办条目 |

---

## 3. 验收

1. `/ai` 可按标题过滤会话；无会话/无匹配可区分。  
2. 未配置 LLM 时见顶栏提示。  
3. 确认卡可展开参数；确认中显示「处理中…」。  
4. 流式对话、团队分析、确认/拒绝仍可用。  
5. `./scripts/check.sh` 绿。

## 4. 风险

- args 可能含敏感字段——仅本机已登录用户可见，与现 summary 同级；不做脱敏（YAGNI）。  
- 会话很多时前端过滤足够（会话量通常小）。
