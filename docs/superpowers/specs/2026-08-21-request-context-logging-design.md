# 统一日志 / 请求上下文（Phase 7）设计

日期：2026-08-21

## 背景

Phase 0–6 后端架构重构（垂直切片）已完成：业务域全部迁入 `app/domains/`、兼容壳拆除、异常统一 `AppError`。对照主 spec 的「横切能力」表，**统一日志 / 请求上下文**（标注 Phase 5+，成功标准「不改业务语义」）尚未落地：

- 当前仅 CORS 中间件；无请求级上下文
- 约 20 个文件用 `getLogger`（29 处日志调用），但无 request_id，异常日志与业务日志无法串联
- 全局异常 handler（`app/api/errors.py`）已记录未捕获异常，但未携带 request_id / method / path / user_id

## 目标（核心：请求可追踪）

1. 每个 HTTP 请求获得唯一 `request_id`，可透传、可回显
2. 现有所有 `getLogger` 输出自动携带 `request_id`（无需逐文件改造）
3. 未捕获异常日志增强：request_id + method + path + user_id
4. **不改业务语义**：不引入依赖、不重写现有日志语句、不改 REST/JWT

## 决策

| 项 | 选择 |
|----|------|
| 核心目标 | 请求可追踪（tracing），非访问日志/审计 |
| request_id 来源 | 优先透传客户端 `X-Request-ID`，无则服务端生成 |
| 日志接入方式 | `logging.Filter` 注入 root handler，一次性覆盖现有 logger |
| 响应头 | 回显 `X-Request-ID` |
| 中间件实现 | 纯 ASGI 中间件（非 `BaseHTTPMiddleware`） |
| 异常日志 | `unhandled_exception_handler` 记录 error 级并带上下文（request_id + method + path + user_id）；业务异常 handler 保持不记录 |

## 组件设计

### 1. `app/core/request_context.py`（新）

```python
@dataclass
class RequestContext:
    request_id: str
    method: str
    path: str
    user_id: str | None = None

_request_ctx: ContextVar[RequestContext | None] = ContextVar("request_ctx", default=None)

def get_request_context() -> RequestContext | None: ...
def get_request_id() -> str: ...
def set_user_id(user_id: str) -> None: ...   # 鉴权后由 deps 调用
```

- `ContextVar` 进程内请求作用域，请求结束 `reset`
- `request_id` 生成：优先透传 `X-Request-ID`（strip 后校验：非空、长度 ≤64、字符集 `[A-Za-z0-9_-]`），非法则生成 `uuid4().hex[:12]`

### 2. `app/core/request_logging.py`（新）

```python
class RequestIdFilter(logging.Filter):
    def filter(self, record) -> bool:
        record.request_id = get_request_id() or "-"
        return True
```

- 格式化串升级为 `"%(asctime)s %(levelname)-7s %(name)s | %(request_id)s | %(message)s"`
- `configure_logging` 挂载 Filter 到 **root handler**（幂等；uvicorn 已接管时同样附加）

### 3. `app/core/logging.py`（改）

- `configure_logging` 增加 `request_id` 字段支持；保持幂等、兼容 uvicorn

### 4. `app/main.py`（改）

- 注册 `RequestContextMiddleware`（CORS 之后、路由之前）

### 5. `app/api/errors.py`（改）

- 仅增强 `unhandled_exception_handler`（当前已记录 method/path，补充 request_id、user_id；request_id 由 Filter 自动带，方法/路径/用户从 `get_request_context()` 读取）
- `AppError` / `HTTPException` / `RequestValidationError` 三个 handler 保持不记录（有意的业务响应，非异常），仅继续 `_json` 输出

### 6. `app/api/deps.py`（改）

- `get_current_user` 成功后调用 `set_user_id(...)`，使后续日志可关联用户

## 数据流

```text
GET /api/v1/watchlist  (X-Request-ID: abc123)
  → RequestContextMiddleware: request_id=abc123 存入 ContextVar
  → deps.get_current_user: set_user_id("u_7")
  → route/service: logger.info(...)  → "abc123 | ..."
  → 服务异常 503 → handler: logger.error("path=/api/v1/watchlist user_id=u_7")
  → 响应头 X-Request-ID: abc123
```

## 错误处理

- 中间件 `finally` 中 `reset(ContextVar)`，防止请求间泄漏
- 中间件自身异常不吞请求（仅记录并 re-raise）

## 测试

| 类型 | 用例 |
|------|------|
| 单元 | `get_request_id`：透传 / 服务端生成 / 非法值回退 |
| 单元 | `RequestIdFilter`：有/无上下文时输出 "-" 或 request_id |
| 集成 | `TestClient` 带 `X-Request-ID` 请求 → 响应头回显；不带 → 生成并回显 |
| 集成 | caplog 断言业务 logger 输出包含 request_id |
| 回归 | 全量 pytest 绿（现有 699 passed, 12 skipped 不变） |

## 非目标

- 访问日志（access log）中间件（uvicorn access log 已覆盖）
- 结构化日志 / JSON 日志 / 日志收集（ELK 等）
- 全库日志语句重写；异步任务（ARQ）request_id 传播（任务自带 job_id）
- 分布式 trace（OpenTelemetry 等）

## 验收

- 全量 pytest 绿
- 带 `X-Request-ID` 请求，业务日志与异常日志均含该 id
- 不带则服务端生成并在响应头回显
- 现有 20 个文件 logger 输出自动带 request_id（Filter 生效）
- 无业务逻辑改动（diff 仅新增 core 文件 + 5 处接入）
