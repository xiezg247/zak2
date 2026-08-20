# 后端架构重构（混合垂直切片）设计

日期：2026-08-20

## 目标

在不改对外 HTTP / JWT / Redis 键 / ARQ job_id 的前提下，把后端从「纯横向分层」演进为「横切横向 + 业务垂直切片」：

- 找代码更容易（对齐前端 `features/` 思路）
- API 变薄，route / service / repository 边界清晰
- 大文件与不合理边界（如 route 直连 repository）随域迁移一并收敛
- 用可分阶段 PR 铺开，先试点再复制模板

## 约束与决策

| 项 | 选择 |
|----|------|
| 范围形态 | 总纲分期（目录结构 + 分层 + 拆大文件 + 横切），按优先级拆 PR |
| 行为变更 | 允许修明显不合理边界；须有测试覆盖与文档说明；业务语义不变 |
| 目录形态 | 混合：`core` / `models` / `integrations` 横向；业务进 `domains/` 垂直切片 |
| 试点域 | `auth` + `channels` |
| 迁移策略 | 兼容壳（thin re-export）+ 域内收口；迁完再拆壳 |
| 非目标 | 不上完整 Clean Architecture / CQRS / 新 DI；不按域拆 `models` 包；不改前端；不扩产品功能；不重写 ops/worker 拓扑 |

## 目标目录

```text
backend/app/
  core/              # 设置、DB、安全、日志、Redis 键、领域异常（横切）
  integrations/      # Tushare / TickFlow / Bilibili 等外部适配
  models/            # SQLAlchemy 模型（暂留横向；可整理文件，不按域搬包）
  domains/           # 业务垂直切片（新增）
    auth/
      router.py
      service.py
      repository.py
      schemas.py
      login_guard.py
    channels/
      router.py
      service.py
      repository.py
      schemas.py
      notify/        # delivery / feishu（渠道主消费者）
  api/
    deps.py          # get_current_user 等横切依赖（不进 domains）
    v1/              # 过渡期：thin re-export → domains.*.router
  worker/            # ARQ / 调度入口（横切）
  strategies/        # 策略算法内核（非 HTTP 域）
  skills/            # 暂不动；AI 工具层后续单独收口
```

## 分层约定（硬规则）

| 层 | 可以依赖 | 禁止 |
|----|----------|------|
| `router` | service、schemas、`api.deps`、`ApiResponse` | 直接用 repository / 写 SQL / 调外部 HTTP |
| `service` | repository、`core`、`integrations`、其它域的 **service 公开 API** | 依赖 FastAPI `Request` / `HTTPException`（用领域异常再映射） |
| `repository` | `models`、`Session` | 业务规则、外部 IO |
| `models` | SQLAlchemy / 基础类型 | 反向依赖 service / api |

域间只经对方 `service` 公开入口；禁止 `domains.A.router` import `domains.B.repository`。

`get_current_user`、JWT、DB session 留在 `api` / `core`，避免 `domains ↔ api` 循环依赖。

## 分期路线图

| Phase | 内容 | 成功标准 |
|-------|------|----------|
| **0** | 约定文档 + `domains/` 骨架 + 导入规则说明 | 空包可 import；本 spec 已落地 |
| **1** | 试点 `auth` + `channels`（薄 API + service + 兼容壳） | 相关测试绿；route 不再直连 repo；HTTP 兼容 |
| **2** | `content`（notes / feed / playbook） | 与前端 features 对齐；API 变薄 |
| **3** | `watchlist`（拆大文件 + 垂直切片） | watchlist 路由职责清晰、行数可控 |
| **4** | `screener` / `market`+`radar`+`emotion` / `backtest` | 按域分 PR |
| **5** | `ops` + worker 边界；横切打磨（异常/日志） | ops 路由薄、job 注册清晰 |
| **6** | 拆除兼容壳；更新 `docs/architecture-p1.md` | 无双路径实现 |

本设计落地后，实现计划优先覆盖 **Phase 0–1**；后续 Phase 各自开 plan/PR。

## Phase 1：试点域改造

### auth

**现状**：`api/v1/auth.py` 直接使用 `UserRepository` + `login_guard` + `create_access_token`。

**目标数据流**：

```text
Router → AuthService → (login_guard + UserRepository + core.security)
                    → TokenResponse / 领域错误 → Router 或全局 handler 映射 HTTP
```

- `POST /login` → `AuthService.login(username, password, ip)`
- `GET /me` → 仍用 `deps.get_current_user`
- `login_guard` 迁入 `domains/auth/`
- `UserRepository` / `schemas/auth` 迁入域内，旧路径 re-export

### channels

**现状**：CRUD 在 router 中直接 `ChannelRepository`；`test` 再调 `services.notify.delivery`。

**目标数据流**：

```text
Router → ChannelService → ChannelRepository
                       → notify.delivery.send_to_channel（test）
                       → ChannelOut / 领域错误
```

- `list/create/update/delete/test` 全部经 `ChannelService`
- `services/notify/*` 实现迁到 `domains/channels/notify/`；`app.services.notify` 保留 re-export，供 `ops.auto_screen` 等未迁调用方继续 import
- 其它域发通知只依赖公开投递函数（经 `domains.channels.notify.delivery` 或兼容壳）
- `models` 中 channel / notify 相关表 **暂不搬**

### 文件迁移清单（Phase 1）

| 从 | 到 |
|----|----|
| `api/v1/auth.py` | `domains/auth/router.py`；`api/v1/auth.py` re-export |
| `services/login_guard.py` | `domains/auth/login_guard.py`；旧路径 re-export |
| `repositories/user.py` | `domains/auth/repository.py`（旧路径 re-export） |
| `schemas/auth.py` | `domains/auth/schemas.py`（旧路径 re-export） |
| `api/v1/channels.py` | `domains/channels/router.py`；`api/v1/channels.py` re-export |
| `repositories/channel.py` | `domains/channels/repository.py`（旧路径 re-export） |
| `schemas/channel.py` | `domains/channels/schemas.py`（旧路径 re-export） |
| `services/notify/*` | `domains/channels/notify/*`；`services/notify` 整包 re-export |

### 错误处理（Phase 1 最小集）

在 `app/core/errors.py` 引入轻量领域异常，并扩展现有 `register_exception_handlers`：

| 异常 | HTTP |
|------|------|
| `NotFound` | 404 |
| `ValidationFailed` | 400 |
| `Unauthorized` / `Forbidden` | 401 / 403 |
| `RateLimited` | 429 |

仅覆盖 auth/channels 已有语义；未迁域可继续 `HTTPException`。

### Phase 1 验收

- 现有相关测试通过（至少含 `test_login_guard`、`test_channels_api`、`test_security` 及 auth/channels 相关用例）
- `domains/*/router.py` 不直接实例化 `*Repository`
- OpenAPI 路径与响应字段不变
- 旧 import 路径仍可用（re-export）

## 横切能力（不压在 Phase 1 一次做完）

| 能力 | 时机 | 做法 |
|------|------|------|
| 领域异常 → HTTP | Phase 1 最小集 | `core/errors` + 扩展 exception handlers |
| deps / JWT / DB | 始终横切 | 不进 `domains` |
| 统一日志 / 请求上下文 | Phase 5+ | 不改业务语义 |
| import 约定文档化 | Phase 0 | 禁止 router→repository |
| 拆超大文件 | Phase 3+ 随域 | 如 `ai_tools`、`strategy_board`、`watchlist` 路由 |

## 兼容、风险与回滚

### 兼容

- 旧模块路径保留 thin re-export，直到该域消费方迁完
- 对外 REST、JWT、渠道 schema、任务 ID、Redis 键不变
- 每域以 pytest 绿为合并门禁

### 风险

| 风险 | 缓解 |
|------|------|
| 双路径漂移 | re-export 只做薄转发；迁完删旧实现 |
| 循环依赖 | deps 留 `api`；domain 不 import `api.v1` |
| 测试漏改 | Phase 1 跑相关全量测试 |
| 模板不适配大域 | Phase 1 后复盘再调约定 |
| 范围膨胀 | 每 Phase 独立 PR；先只做 0–1 |

### 回滚

- 壳仍在：恢复 `api/v1` 实体实现并移除对应 `domains/*`
- 壳已删：revert 整 PR；Phase 1 保持小 PR 面

## 总纲成功标准

1. 本 spec 成为可执行分期总纲
2. Phase 1：`auth` / `channels` 符合分层约定，测试绿，HTTP 兼容
3. 后续域有可复制的目录与 PR 模板

## 实现顺序（进入 plan 后）

1. Phase 0：建 `domains/` 骨架与约定备注（可与 Phase 1 同一 PR）
2. Phase 1a：`core/errors` + handler
3. Phase 1b：迁 `auth`
4. Phase 1c：迁 `channels`（含 notify）
5. 跑测试、更新 `architecture-p1.md` 中「结构」一行指向本 spec（完整 architecture 刷新留 Phase 6）
