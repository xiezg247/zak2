# 消息渠道（飞书 Webhook 接入）设计

日期：2026-08-19

## 目标

在 Web 端新增「消息渠道」菜单，允许用户扫码/填入飞书自定义机器人 Webhook 完成接入，并把选股/盘后结果推送到已接入渠道。首版只做飞书，暂不对接微信。

## 范围

### 首版包含

- 新表 `app.notify_channel` 存储渠道配置（按用户隔离，支持多渠道）
- 飞书自定义机器人 Webhook 发送实现（httpx 同步调用，10s 超时）
- 渠道 CRUD + 测试发送 API（`/api/v1/channels`）
- 投递结果写入既有 `app.notify_delivery_log`
- 选股（盘中/盘后）执行完成后推送 Top 列表
- 前端独立「消息渠道」页面 + 侧边栏入口

### 首版不做

- 微信接入
- 推送 AI 研报、风险预警等其他事件
- 双向交互（微信/飞书里发指令给系统）
- 飞书开放平台应用（App ID/Secret）方式，仅自定义机器人 Webhook

## 数据模型

新表 `app.notify_channel`（Postgres）：

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| id | uuid | PK（应用层生成） |
| user_id | uuid | NOT NULL，index，归属用户 |
| channel_type | text | NOT NULL，当前仅 `feishu` |
| name | text | NOT NULL，显示名称 |
| config_json | text | NOT NULL，`{"webhook_url": "..."}` |
| enabled | bool | NOT NULL，默认 true |
| created_at | text | NOT NULL |
| updated_at | text | NOT NULL |

沿用现有 alembic 迁移风格（见 `007_web_team_reports.py`），新迁移 `012_notify_channel`。

## 后端

### 文件与职责

| 文件 | 职责 |
|---|---|
| `app/models/channel.py` | `NotifyChannel` 模型，注册进 `models/__init__.py` |
| `alembic/versions/012_notify_channel.py` | 建表 + user_id 索引 |
| `app/schemas/channel.py` | ChannelOut / ChannelCreate / ChannelUpdate / ChannelTestOut |
| `app/services/notify/feishu.py` | `send_feishu_webhook(webhook_url, title, text)`：httpx 10s 超时，校验 `code == 0` |
| `app/services/notify/delivery.py` | `deliver_text(db, user_id, event_type, title, text)` 遍历启用渠道逐个发送并写投递日志；`send_to_channel(...)` 单渠道发送 + 记录 |
| `app/api/v1/channels.py` | CRUD + test，注册进 `api_router` |
| `app/services/ops/auto_screen.py` | 选股成功后调用 `deliver_text` 推送结果 |

### API

- `GET /channels` — 当前用户渠道列表
- `POST /channels` — 新增（校验 webhook URL 必填、name 必填）
- `PATCH /channels/{id}` — 改名 / 改 webhook / 启停（校验归属）
- `DELETE /channels/{id}` — 删除（校验归属）
- `POST /channels/{id}/test` — 发送测试消息，返回真实成败原因

所有路由走 `get_current_user`，仅操作当前用户自己的渠道。

### 选股推送集成

在 `_run_auto_screen` 成功分支（`save_job_run_meta(...last_success=True)` 之后）调用推送：

```text
📊 盘后选股完成
配方 post_close_multi 命中 12 只（扫描 4800，run=xxx）
1. 600519 贵州茅台 +2.31%
2. ...
```

- 只推送命中 Top 列表（从 `result` 中取行）
- 推送失败只写投递日志（`status=error`），**绝不抛异常影响选股主流程**
- 若该用户没有任何启用渠道则跳过

### 错误处理

- Webhook 网络失败 / 非 200 / 飞书返回 code != 0 → 记 `status=error` + 原因
- 发送成功 → 记 `status=ok`

## 前端

| 文件 | 职责 |
|---|---|
| `frontend/src/api/channels.ts` | `channelApi`：list / create / update / remove / test |
| `frontend/src/views/ChannelsView.vue` | 渠道列表 + 新增/编辑弹窗 + 测试/启停/删除 |
| `frontend/src/components/AppShell.vue` | 「系统」分组新增「消息渠道」菜单 |
| `frontend/src/components/NavIcon.vue` | 新增 `channels` 图标 |
| `frontend/src/router/index.ts` | 新增 `/channels` 路由 |

页面形态：

- 头部说明 + 「新增渠道」按钮
- 渠道卡片：名称、类型徽章（飞书）、Webhook 地址（脱敏显示）、启用开关、测试按钮、删除
- 新增/编辑弹窗：名称 + Webhook URL + 启用
- 测试结果即时反馈（成功/失败原因展示）
- 删除需二次确认

## 测试

- 后端单测：webhook 发送（mock httpx）、delivery 记录、channels CRUD 归属校验
- 前端 `vue-tsc` + `eslint` 通过

## 非目标（防范围蔓延）

- 不做多渠道模板、消息模板管理
- 不做微信
- 不做渠道的加解密（webhook 明文存储，与现有表风格一致）
