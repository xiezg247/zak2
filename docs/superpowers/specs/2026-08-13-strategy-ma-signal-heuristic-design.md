# 策略信号日 K 双均线启发式设计

日期：2026-08-13  
状态：已批准（方案 A：独立 MA 模块 + 升级 warm job；保留 Redis→PG 桥）  
范围：仅 zak2；不写 position cache；不移植桌面 ShortBreakout

## 背景

`warm_watchlist_strategy_cache` 已做 Redis→PG 桥，但无真算；策略看盘只读 cache。回测已有日 K 双均线（`double_ma` / `_sma`）。本刀用日 K 启发式写入 `watchlist_signal_cache`，使看盘在无 Redis 桌面信号时仍可读。

## 目标

1. 日 K 双均线启发式：全站自选并集 × 各 `config_key` → buy/sell/hold，写 `cache.watchlist_signal_cache`。  
2. 升级 `warm_watchlist_strategy_cache`：先 Redis→PG 桥，再真算覆盖/补齐。  
3. payload 对齐策略看盘字段；文案标明「启发式」。  
4. 更新 catalog、看盘空 cache `note`、smoke、roadmap **#29**；`./scripts/check.sh` 绿。

## 非目标

- 移植桌面 `AshareShortBreakoutStrategy` 全规则  
- 写 `watchlist_position_cache` / 持仓出场信号  
- 1m 下载、下单、`needs_user_id`、默认启用定时  
- 改 zak / vnpy-*；引入 arq/Celery

## 决策摘要

| 项 | 选择 |
|----|------|
| 算法 | 日 K 双均线金叉/死叉（深度 1） |
| 标的池 | 全站自选并集（`list_watchlist_symbols`，可截断） |
| config_key | 默认 + 用户 `signal_config` 偏好聚合 |
| 与桥关系 | 先桥后算；真算覆盖同 key |
| position | 本刀不做 |

---

## 1. 算法模块 `strategy_signal_ma`

### 1.1 解析 `config_key`

格式：`{ClassName}:{fast}:{slow}`（与 `strategy_board.resolve_config_key` 一致）。  
`fast`/`slow` 非法或 `fast >= slow` → 该 key 跳过。

### 1.2 读 K 线

对 `(symbol, exchange)` 读 `interval=d`，条数 `limit = min(200, max(slow * 3, 60))`。  
不足 `slow + 1` 根有效收盘 → 返回 skip（不抛）。

实现可复用 `bars.load_bars` 的查询逻辑，或直接 SQL/ORM；缺数据时**不要** 404 打断整 job（封装为「可选加载」）。

### 1.3 SMA 与信号

- SMA 规则对齐 `backtest_engine._sma`（可抽共享或复制最小实现）。  
- 取最近两根均有 fast/slow 的 bar：  
  - 昨 `fast≤slow` 且今 `fast>slow` → `buy`  
  - 昨 `fast≥slow` 且今 `fast<slow` → `sell`  
  - 否则 → `hold`

### 1.4 Payload

写入 JSON 字符串，字段至少：

| 字段 | 说明 |
|------|------|
| `signal` | `buy` / `sell` / `hold` |
| `signal_label` | 买入 / 卖出 / 观望 |
| `vt_symbol` | |
| `as_of` / `signal_date` | 最近 bar 日期 |
| `last_close` | |
| `ma_gap_pct` | `(fast-slow)/slow*100` |
| `volume_ratio_5d` | 有量则算近 5 日均量比，否则省略或 null |
| `reason_summary` | 如 `5/10 日均线金叉（启发式）` |
| `strength` | 可选 `abs(ma_gap_pct)` |

**不**写 position cache。

### 1.5 纯函数接口（建议）

```python
def compute_ma_signal(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    fast: int,
    slow: int,
    vt_symbol: str,
    as_of: str,
) -> dict[str, Any] | None:
    """不足数据返回 None。"""
```

---

## 2. Job：`warm_watchlist_strategy_cache`

### 2.1 流程

1. 现有 Redis→PG 桥（`written_signals` / `written_positions` 统计保留）。  
2. `pool = list_watchlist_symbols(db)[:POOL_CAP]`（建议 `POOL_CAP=500`）。  
3. `config_keys = _list_config_keys(db)`。  
4. 对每个 `config_key` × 每个标的：加载日 K → `compute_ma_signal` → upsert `watchlist_signal_cache`（`bar_as_of`、`updated_at`、`payload`）。  
5. `db.commit()`；`save_job_run_meta(last_success=True)`（无灾难性异常时）。

### 2.2 返回

```text
{
  success: True,
  skipped: False,
  message,  # 须含「双均线启发式」
  written_signals,   # 桥写入数
  written_positions, # 桥写入数
  computed,          # 真算成功写入数
  skipped_bars,      # 因缺 K / 不足根数跳过
}
```

空池或全缺 K：仍 `success=True`，`computed=0`。

### 2.3 Catalog

描述改为：`Redis 桥 + 日 K 双均线启发式 → watchlist_signal_cache（Web 可跑）`。

---

## 3. 看盘 note（`strategy_board.py`）

更新空信号文案，去掉「尚未接入策略引擎预热」：

- 引导：可 Ops 跑 `warm_watchlist_strategy_cache`（双均线启发式），或确认 Redis/PG 已有 cache。  
- 有信号时 note 逻辑不变（可空）。

---

## 4. 测试

| 文件 | 要点 |
|------|------|
| `test_strategy_signal_ma.py` | 金叉/死叉/hold；不足数据 → None |
| `test_ops_warm_watchlist_strategy.py` | mock 桥 + mock 计算 → `computed`；扩展断言 message 含启发式 |

---

## 5. 文档

- smoke：`warm_watchlist_strategy_cache` 含启发式真算；有日 K 自选后看盘可见信号。  
- roadmap：**#29** 链本 spec。

---

## 6. 验收

1. Ops 跑 warm 后，有日 K 的自选在策略看盘可见启发式信号。  
2. Redis 桥仍工作；缺 K 标的跳过不失败。  
3. smoke / #29；`./scripts/check.sh` 绿。

## 明确不做（复述）

ShortBreakout 全量；position cache；1m；默认开定时；zak / vnpy-*。
