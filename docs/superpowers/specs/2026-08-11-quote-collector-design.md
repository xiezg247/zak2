# zak2 独立行情采集（Quote Collector）设计

日期：2026-08-11  
状态：已批准（方案 B：独立 Collector + 可插拔 Provider）  
范围：仅 zak2；不改 zak；不 import `vnpy_*`

## 目标

1. **zak2 自给自足**：盘中全市场快照写入 Redis，不再依赖 `zak CLI job run collect_quotes`。  
2. **采集与 API 进程分离**：重活在独立 `quote-collector` 进程；FastAPI 只读 + 管控。  
3. **读路径零破环**：继续写现有键 `zak:quote:*` / `zak:rank:*` / `zak:meta:*` / `zak:notify:quotes`，现有 `QuoteStore`、选股、雷达、WS Hub 不用改语义。  
4. **可插拔源**：第一刀默认 **TickFlow**（官方 `tickflow` PyPI 包，非 `vnpy_tickflow`）；接口预留第二刀 Tushare / 其它 Provider。

## 非目标（本刀）

- 不把全市场采集塞进 uvicorn / 内嵌 APScheduler 主路径  
- 不 import `vnpy_*` / 不调 zak 子进程  
- 不推 Tick / 五档；WS 仍只推 `seq` → 前端拉 REST  
- 不在 collector 内做 Tushare 因子 enrich（换手/量比/净流入等）——见 [行情 enrich 设计](./2026-08-11-quote-enrich-design.md)  
- 不迁键前缀到 `zak2:*`；不做自建 Redis 强制替换宿主机  
- 不与 zak 采集双写共存（文档约定：**同一 Redis 只跑一个采集端**）  
- 不做 `change_speed_5m` 基线、L1 内存 cache（桌面专有优化）

## 架构

```text
app.universe (PG)
       │
       ▼
[quote-collector] ── Provider.fetch(symbols) ──▶ QuoteSnapshot[]
       │
       ├── RedisQuoteWriter
       │      HASH zak:quote:{TF_SYMBOL}
       │      ZSET zak:rank:{field}
       │      meta updated_at / quote_count / seq
       │      PUBLISH zak:notify:quotes  {seq}
       │
       └── heartbeat  zak2:collector:heartbeat
              ▲
              │  force / ping（可选）
FastAPI Ops ──┘  PUBLISH zak2:collector:cmd
       │
Vue Ops / 现有 QuoteStore / WS Hub（只读侧不变）
```

### 进程边界

| 进程 | 职责 |
|------|------|
| `uvicorn`（API） | 读 Redis；健康展示 heartbeat；发 force 命令；**不**跑全市场拉行情 |
| `quote-collector` | 交易时段循环：universe → Provider → Writer → notify；听 cmd |

入口：`uv run python -m app.quote_collector`（或 `scripts/quote_collector.sh` 薄包装）。  
`docker-compose` 可选增加 `quote-collector` service（与 api 同 image / 同 env，command 不同）。

## 组件

### 1. `QuoteSnapshot`（zak2 自有 dataclass）

最小字段（与现读侧对齐）：

`symbol`（TickFlow 形 `SHSE.600519`）、`name`、`last_price`、`prev_close`、`open_price`、`high_price`、`low_price`、`change_amount`、`change_pct`、`turnover_rate`、`volume`、`amount`、`amplitude`、`volume_ratio`、`net_mf_amount`、`limit_times`、`trade_time`、`industry`、`total_mv`、`circ_mv`

第一刀 Provider 可只填价量涨跌幅等；因子类字段缺省 0 / 空（与现「无 enrich」行为一致）。

### 2. `QuoteProvider` Protocol

```python
class QuoteProvider(Protocol):
    name: str
    def fetch(self, symbols: list[str]) -> dict[str, QuoteSnapshot]: ...
```

- **`TickFlowProvider`（本刀）**：依赖 `tickflow>=0.1.22`（optional extra `collector` 或直接进主依赖）；`TICKFLOW_API_KEY` 有则 `TickFlow(api_key=…)`，无则 `TickFlow.free()`（文档注明免费档可能无全市场实时）。批量大小默认 **80**，并发 workers 默认 **4**（env 可调，夹逼 1–8）。  
- **`TushareRtProvider`**：本刀只留 Protocol / 注册钩子，实现放第二刀。

符号：universe 行转为 TickFlow 符号（`SSE→SHSE`、`SZSE→SZSE`、`BSE→BJSE`）；与现 `_to_vt_symbol` 逆映射一致。

### 3. `RedisQuoteWriter`

- 键前缀保持 **`zak`**（兼容读侧）。  
- 写 HASH：本刀固定写**长 field**（`last_price` 等）；`QuoteStore.normalize_hash` 已兼容短/长。不引入 blob / compact env，降低复杂度。  
- 每轮：`INCR zak:meta:seq` → pipeline `HSET` 全量 → 重建主榜 ZSET（至少 `change_pct` / `turnover_rate` / `amount` / `volume` / `amplitude`；稀疏榜 `volume_ratio` / `net_mf_amount` / `limit_times` 仅当值有效）→ `SET meta:updated_at` / `meta:quote_count` → `PUBLISH zak:notify:quotes` 字符串 seq。  
- **本刀始终 publish**（不依赖桌面 `ZAK_QUOTE_REDIS_NOTIFY`），保证 Web WS 可用。  
- 空 quotes：不写、不 incr、不 publish。

### 4. Universe

- 读 `app.universe`（与 `sync_universe` 同表）；空则本轮 skip，message 提示先跑同步。  
- 可选合并固定指数列表（若 TickFlow 需要；无则仅股票）。

### 5. 交易时段

zak2 自研薄判断（`Asia/Shanghai`）：

- 工作日且时刻落在 **09:15–11:30** 或 **13:00–15:05**（含集合竞价缓冲；收盘后短暂可采）。  
- 非交易时段：循环 sleep，不调 Provider（`force` 命令除外，强制采一轮）。  
- 不依赖 zak 日历表做节假日（可后续接 `trade_calendar`；本刀用周一–周五近似即可，文档注明）。

### 6. 主循环

配置：

| env | 默认 | 说明 |
|-----|------|------|
| `QUOTE_COLLECTOR_ENABLED` | true（进程内） | 进程启动即跑；false 则立刻退出码 0 |
| `QUOTE_COLLECT_INTERVAL_SEC` | 30 | 夹逼 5–300 |
| `QUOTE_PROVIDER` | `tickflow` | 本刀仅实现该值 |
| `TICKFLOW_API_KEY` | 空 | 见 Provider |
| `REDIS_URL` / `DATABASE_URL` | 同 API | 共用 |

流程：heartbeat →（交易时段或 force）load universe → fetch → write → 清 force 标志 → sleep interval。  
异常：记日志 + heartbeat.`last_error`；不退出进程（短暂错误可恢复）。连续配置级失败（无 Redis）可指数退避，上限 60s。

### 7. 心跳与控制（Redis）

| Key / Channel | 内容 |
|---------------|------|
| `zak2:collector:heartbeat` | JSON：`ts`（ISO）、`pid`、`provider`、`status`（`idle`/`collecting`/`skipped`/`error`）、`last_count`、`last_duration_ms`、`last_error`、`interval_sec` |
| `zak2:collector:cmd` | Pub/Sub 文本：`force` = 下一轮或立即强制采集 |

TTL：heartbeat 建议 `SET` 带 EX=120；API 若 `ts` 过旧（>90s）视为 collector 未运行。

## Ops / API / 前端

### Health

`GET /ops/health` 增加 `quote_collector` 对象：

- `running`：heartbeat 新鲜  
- `provider` / `status` / `last_count` / `updated_at`（可与 redis quote meta 并列）  
- `hint`：未运行时「请启动 `python -m app.quote_collector`」

### 强制采集

`POST /api/v1/ops/collector/force`（需登录）：

- `PUBLISH zak2:collector:cmd force`  
- 若无新鲜 heartbeat → 200 但 `success=false`，文案提示 collector 未启动  
- **不**把 `collect_quotes` 加入 `RUNNABLE_JOB_IDS`（避免在 API 内拉全市场）

### 目录展示

`ops_catalog` 中 `collect_quotes` 行：`runnable=false` 保持；`run_hint` 改为指向 zak2 collector（不再只写 zak CLI）。可选增加只读「采集进程」卡片（heartbeat + 强制按钮）。

### 前端 `OpsView`

- 健康区展示 collector 状态  
- 「强制采一轮」按钮调 force API  
- README / smoke：启动步骤改为 API + collector（zak CLI 采集改为可选兼容）

## 配置与依赖

- `backend/pyproject.toml`：增加 `tickflow[all]>=0.1.22`（或 optional-dependencies `collector`；若 optional，文档写明 `uv sync --extra collector`）。**推荐直接进主依赖**，避免 Ops 有按钮却未装包。  
- `.env.example`：补 `TICKFLOW_API_KEY`、`QUOTE_COLLECT_INTERVAL_SEC`、`QUOTE_PROVIDER`。  
- `docker-compose.yml`：本刀增加 `quote-collector` service（与 api 同 Dockerfile，`command` 改为 `python -m app.quote_collector`；`depends_on` redis 仍可为宿主机 Redis）。

## 测试

全部 mock，不打真 TickFlow / 真 Redis 集成（可用 fakeredis 若已有，否则 mock redis client）。

| 测项 | 断言 |
|------|------|
| TickFlow 行解析 | change_pct 等比例与桌面一致（×100 若 SDK 给小数） |
| Writer | 写入调用含 quote key、rank zadd、meta、publish |
| 空 quotes | 不 incr / 不 publish |
| 时段 | 非交易 skip；force 仍采 |
| 心跳过期 | health `running=false` |
| force API | publish 被调用 |

## 文档

- `gap-vs-desktop.md`：行情采集常驻 → **有（薄）**（zak2 collector；键兼容；无 enrich / 无桌面 L1）  
- 「建议下一刀」：Tushare enrich 因子 或 只读持仓/信号工具  
- `smoke-checklist.md`：启动 collector；Ops 可见 heartbeat；强制采后 `quote_count`/`updated_at` 更新；自选/市场有行情  
- `README.md`：去掉「必须先 zak collect_quotes」为唯一路径  

## 验收

1. 仅启动 Redis + PG + API + collector（无 zak CLI 采集）时，盘中 `quote_count>0`，市场涨幅榜 / 自选行情可读。  
2. 采一轮后 WS 或轮询能刷新（notify seq 递增）。  
3. Ops force：collector 在时成功；未启动时明确失败文案。  
4. 相关 pytest 绿；`npm run build` 绿。  

## 分期（本刀之后）

| 刀 | 内容 |
|----|------|
| 2 | Tushare enrich（换手/市值/净流入）+ 可选 `TushareRtProvider` |
| 3 | compose 默认带 collector；键前缀 / 自有 Redis 迁移评估 |

## 澄清记录

- 用户确认独立演进 + 方案 B；「继续」进入本设计。  
- 第一刀默认源：**TickFlow**（`tickflow` 包）；Tushare 作后续 Provider。  
- 与 zak 采集互斥，不双写同一 Redis。  
