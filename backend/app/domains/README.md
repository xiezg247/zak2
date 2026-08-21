# domains 约定

## 分层

| 层 | 可以依赖 | 禁止 |
|----|----------|------|
| router | service、schemas、`app.api.deps`、`ApiResponse` | repository、SQL、外部 HTTP |
| service | repository、`core`、`integrations`、其它域 service 公开 API | FastAPI `HTTPException` / `Request` |
| repository | `models`、`Session` | 业务规则、外部 IO |

## 兼容

迁移期间旧路径（`app.api.v1.*`、`app.repositories.*`、`app.services.notify`）仅允许 thin re-export。

详见 `docs/superpowers/specs/2026-08-20-backend-architecture-refactor-design.md`。

## 已迁入

- `auth` / `channels`（Phase 1）
- `content`（notes / feed / playbook / notify_log，Phase 2）
- watchlist（自选/分组/持仓/信号面板/trading_risk，Phase 3）
- screener（选股 schemas/repository/services，Phase 4 Task 1）
- screener 薄 router（Phase 4 Task 2）
- market / radar / emotion（行情/雷达/情绪服务与 market schemas，Phase 4 Task 3）
- market / radar / emotion 薄 router（Phase 4 Task 4）
- backtest（schemas/repository/services/薄 router，Phase 4 Task 5）
- auto_schedules（自动选股计划 CRUD/执行/轮询，Phase 5 Task 1–2）
- ops / jobs 路由与 services/ops 异常统一（HTTPException → AppError，Phase 5 Task 3–4）
