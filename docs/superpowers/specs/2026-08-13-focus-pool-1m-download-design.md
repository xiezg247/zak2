# 关注池 1m K 真下载设计

日期：2026-08-13  
状态：已批准（方案 A：扩展 bar_download + 升级 fill_focus_pool_minute）  
范围：仅 zak2；自选池截断；可配置 lookback / max symbols

## 背景

`fill_focus_pool_minute` 目前仅盘点 `dbbaroverview`（d/1m），message 含「1m 下载未接入」。日 K 已有 `bar_download`（Tushare `daily` → `dbbardata`）。本刀接入 Tushare `stk_mins`（freq=`1min`）写入 `interval=1m`。

## 目标

1. `stk_mins` → `public.dbbardata`（`interval=1m`）+ 刷新 `dbbaroverview`。  
2. 升级 `fill_focus_pool_minute`：对自选池真下载，不再「仅盘点」。  
3. 可配置：`FOCUS_1M_LOOKBACK_DAYS`（默认 5）、`FOCUS_1M_MAX_SYMBOLS`（默认 50）。  
4. catalog / smoke / roadmap **#30**；`./scripts/check.sh` 绿。

## 非目标

- 全市场 1m、5m/15m/30m/60m、实时盘中推送  
- 改 zak / vnpy-*；引入 arq/Celery；默认启用定时  

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：扩展 `bar_download` + 升级 fill job |
| 窗口 | 最近 N 个交易日（env，默认 5，clamp 1–20） |
| 池大小 | env 默认 50（clamp 1–500） |
| 接口 | Tushare `stk_mins`，`freq=1min` |

---

## 1. `bar_download` 扩展

### 1.1 常量与 overview

- `INTERVAL_1M = "1m"`（日 K 仍为 `INTERVAL_DAILY = "d"`）。  
- `refresh_overview(db, *, symbol, exchange, interval=INTERVAL_DAILY)`：按传入 interval 统计/删除/插入 overview（去掉硬编码仅 `d`）。  
- 现有日 K 调用点传入默认即可，行为不变。

### 1.2 拉取

```python
def fetch_minute_rows(
    *,
    ts_code: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    # ts.query("stk_mins", {
    #   "ts_code", "freq": "1min",
    #   "start_date": "YYYY-MM-DD HH:MM:SS",
    #   "end_date": "YYYY-MM-DD HH:MM:SS",
    # }, fields="ts_code,trade_time,open,high,low,close,vol,amount")
```

- 单次最大约 8000 行。lookback≤10 时多数标的一日约 240 根，整段通常够用。  
- 若返回触顶或需更稳：按交易日切分循环（实现允许按日拆；测试可用 mock）。

### 1.3 写入

```python
def upsert_minute_bars(db, *, symbol, exchange, rows) -> int:
    # trade_time → datetime；interval=1m
    # DELETE + INSERT 同 (symbol, exchange, interval, datetime)
    # 有写入则 refresh_overview(..., interval=INTERVAL_1M)

def download_minute_bars(db, *, symbol, exchange, start: date, end: date) -> int:
    # start 09:00:00 ~ end 19:00:00（或当日收盘窗口）
    # fetch + upsert
```

---

## 2. Job：`fill_focus_pool_minute`

### 2.1 配置

| Env | 默认 | Clamp |
|-----|------|-------|
| `FOCUS_1M_LOOKBACK_DAYS` | 5 | 1–20 |
| `FOCUS_1M_MAX_SYMBOLS` | 50 | 1–500 |
| sleep | 复用 `BARS_FILL_SLEEP_SEC` 语义（或同名读取） | |

### 2.2 流程

1. `ts.require_token()`；失败 → `{success:False, skipped:True, message}`。  
2. `pool = list_watchlist_symbols(db)[:MAX]`。  
3. 用交易日历取最近 `LOOKBACK` 个开市日 → `start_date`/`end_date`。  
4. 对每个标的：若无 `1m` overview，或 overview.`end` 早于最近已收盘交易日 → 调用 `download_minute_bars`；否则 skip。  
5. 单标失败记入 `failed`，sleep 后继续。  
6. 再盘点 `with_daily` / `with_1m` / `missing_1m`。  
7. `save_job_run_meta`；成功路径 `last_success=True`（有下载或全 skip 补齐亦成功；无 token 为 False）。

### 2.3 返回

```text
{
  success, skipped,
  pool_size, downloaded, bars_added, failed: list,
  with_daily, with_1m, missing_1m,
  lookback_days, max_symbols,
  message  # 不得含「1m 下载未接入」
}
```

### 2.4 Catalog

改为：`自选关注池 1m K 增量下载 → dbbardata（Web 可跑）`。

---

## 3. 测试

| 范围 | 要点 |
|------|------|
| `refresh_overview` / upsert 1m | mock execute；interval=`1m` |
| `fetch_minute_rows` | mock `ts.query` 参数含 `stk_mins` / `1min` |
| job 无 token | skipped |
| job 下载 | mock download → `downloaded`/`bars_added`；message 无「未接入」 |

---

## 4. 文档

- smoke：Ops 跑 `fill_focus_pool_minute` 可下载（需 token + 分钟权限）；无 token 可 skipped；不再「仅盘点/未接入」。  
- roadmap：**#30** 链本 spec。

---

## 5. 验收

1. 有权限时，跑后 `1m` overview 增加；`GET bars?interval=1m` 可读。  
2. 无 token 诚实 skipped；部分标的失败不拖垮整 job。  
3. smoke / #30；`./scripts/check.sh` 绿。

## 明确不做（复述）

全市场 1m；其它分钟周期；实时推送；默认开定时；zak / vnpy-*。

## 备注

Tushare 分钟数据常需**单独分钟权限**；无权限时 Tushare 返回错误 → job 记 failed/message，不伪装成功写入。
