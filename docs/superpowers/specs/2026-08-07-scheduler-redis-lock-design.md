# 内嵌调度 Redis job 锁（防双跑）设计

日期：2026-08-07  
状态：已批准（方案 A：每 job 触发时 SET NX + TTL）  
范围：仅 zak2；不改 zak；Redis 不可用则跳过 job（不降级无锁执行）

## 目标

多 API 副本各自跑 APScheduler 时，同一 `job_id` 同一时刻只有一个实例真正执行 runner。

## 非目标

- 启动期选主（仅 leader 注册 cron）
- PG advisory lock / 其它协调中间件
- Redis 挂时降级无锁执行（会双跑）
- 按 job 定制 TTL 表（本刀统一默认 TTL）
- 改 zak 桌面调度

## 机制

### Key / Token

- Key：`zak2:scheduler:lock:{job_id}`
- Value（token）：`{hostname}:{pid}:{short_uuid}`
- TTL：默认 **1800** 秒；Settings `scheduler_lock_ttl_seconds`（env `SCHEDULER_LOCK_TTL_SECONDS`），夹逼 **[60, 7200]**

### API（服务层）

`backend/app/services/scheduler_lock.py`：

- `make_token() -> str`
- `clamp_ttl(raw: int) -> int`
- `try_acquire(job_id: str, *, token: str, ttl: int | None = None) -> bool`  
  - `SET key token NX EX ttl`  
  - Redis 异常 → `False`（调用方跳过）
- `release(job_id: str, token: str) -> None`  
  - Lua：`if GET==token then DEL`（防误删他人锁）  
  - Redis 异常：打日志，不抛崩 job finally

### 接入 `_run_job`

顺序：

1. 进程内 `threading.Lock`（现有，防同进程重入）
2. `token = make_token()`；`try_acquire(job_id, token=token)`  
   - 失败 → info/warning 日志 skip，释放进程锁，return  
3. 执行现有 runner 逻辑  
4. `finally`：`release(job_id, token)` + 释放进程锁 + 清 `_running`

手动 Ops「立即执行」**不走**此锁（或另议）：本刀只包 `embedded_scheduler._run_job`。若立即执行也走同一 runner，可不加分布式锁（运维显式操作）；**仅定时路径加锁**。

## 配置与可观测

- Settings 新增 `scheduler_lock_ttl_seconds: int = 1800`
- `.env.example` 注释
- `ops_health.health_snapshot` 增加薄字段：

```json
"scheduler_lock": {
  "backend": "redis",
  "ttl_seconds": 1800,
  "key_prefix": "zak2:scheduler:lock:"
}
```

无持锁列表 UI；无新前端页。

## 测试

- `try_acquire` 成功（mock redis SET 返回 True）
- 第二次 acquire 失败（SET 返回 None/False）
- `release` 只删匹配 token（Lua 或 mock）
- Redis 抛错 → acquire False，不执行
- `_run_job`：未获锁时不调用 runner（patch）
- 不打真 Redis（可用 fakeredis 或 MagicMock）

## 文档

- gap：内嵌调度「有 Redis job 锁；多副本防双跑；Redis 不可用则跳过」
- smoke / README：多副本依赖 Redis；锁失败/Redis 挂则定时 job 跳过

## 验收

1. 单测覆盖抢锁/释放/异常跳过  
2. 未获锁不跑 runner  
3. pytest + `npm run build` 绿  
