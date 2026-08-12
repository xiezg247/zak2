# Feed 时间线过滤与空态 UX 设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端；时间线为主 + 无订阅轻引导）  
范围：仅 zak2 `FeedView`；不改 Feed API / 订阅 CRUD / B 站同步 job

## 背景

信息流已有 mid 添加、关键词搜 UP、开关/删除订阅、点开已读。时间线无标题过滤、无「仅未读」、空态未区分无订阅 / 无动态 / 无匹配，也无 Ops 同步入口提示。

## 目标

1. 时间线：标题/作者/摘要过滤 + 「仅未读」。  
2. 空态四分：加载中 / 无订阅 / 有订阅无动态（去 Ops）/ 无匹配。  
3. 无订阅时左侧一句引导（搜 UP 或填 mid）。

## 非目标

- 改 `/api/v1/feed/*` 契约或分页  
- 订阅名过滤（方案 B）、批量标已读、页内强制同步 API  
- 改 `sync_bilibili_feed` 实现或 Cookie 配置 UI

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 `displayedItems` |
| 管道 | `items` → filter(query) → unreadOnly → 列表 |
| 无动态 | 文案 + `RouterLink` 去 Ops（`sync_bilibili_feed`） |
| 订阅侧 | 仅无订阅轻引导，不加过滤框 |

---

## 1. UI 行为

### 1.1 过滤条（右侧，有 `items.length` 时）

- 输入框 placeholder「过滤标题/作者」  
- 开关或按钮「仅未读」（`unreadOnly` boolean）  
- `query` trim 后匹配 `title` / `author_name` / `summary`（大小写不敏感）  
- `unreadOnly` 时保留 `!is_read`

### 1.2 数据流

```
items (API, 已按 subId 过滤) → text filter → unread filter → displayedItems → v-for
```

`subId` / `load` / `openItem` / 添加删除搜索 **不变**。

### 1.3 空态

| 条件 | 左侧 | 右侧 |
|------|------|------|
| `loading` | — | 「加载中…」（可盖住列表区） |
| `!loading && !subs.length` | 现有表单 + 一句「先搜索或填写 mid 添加订阅」 | 「暂无订阅」 |
| `subs.length && !items.length` | 不变 | 「暂无动态」+ 去 Ops 提示 `sync_bilibili_feed` |
| `items.length && !displayedItems.length` | 不变 | 「无匹配动态」；过滤条仍可见 |

错误态保持现有 `error` 行。

### 1.4 点开行为

过滤隐藏某条不影响：仍可在「全部/取消仅未读」后看到；已读标记逻辑不变。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/FeedView.vue` | `displayedItems`、过滤条、空态、样式 |
| `docs/smoke-checklist.md` | `/feed` 检查项 |
| `docs/product-roadmap.md` | 近期待办条目 |

---

## 3. 验收

1. `/feed` 有动态时可过滤与「仅未读」；无匹配文案正确。  
2. 无订阅 / 无动态 / 加载空态可区分；无动态可见去 Ops。  
3. 搜 UP、添加、删除、开关、点开外链仍可用。  
4. `./scripts/check.sh` 绿。

## 4. 风险

- 无 Cookie 时 Ops 同步仍可能 skipped——空态只给路径，不保证拉到数据。  
- `summary` 参与过滤可能较宽——与「标题/作者」placeholder 略宽，可接受（功能正确）。
