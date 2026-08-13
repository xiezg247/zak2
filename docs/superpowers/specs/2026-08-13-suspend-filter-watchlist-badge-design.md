# 停牌硬过滤 + 自选角标设计

日期：2026-08-13  
状态：已批准（方案 1：共享停牌集合 + apply_hard_filters 扩参；自选名称旁「停」）  
范围：仅 zak2；读 `symbol_suspend_days`；不改 Ops sync job；不下单

## 背景

硬过滤 `exclude_suspended` 默认开启，但 Redis 无停牌字段，`apply_hard_filters` 直接跳过。Ops `sync_suspend_daily` 已写入当日停牌表，选股与自选均未消费。

## 目标

1. 选股硬过滤在有当日停牌数据时真正剔除停牌标的。  
2. 自选列表名称旁显示「停」标签。  
3. 无停牌表数据时宽松：不剔除、不标停。  
4. 更新 smoke 与路线图。

## 非目标

- 改 `sync_suspend_daily` / 默认启用定时  
- 独立停牌列 / 列偏好  
- 缺数据时 400 阻断选股或强制警告条  
- 上市日 `exclude_new_listing`（仍跳过）

## 决策摘要

| 项 | 选择 |
|----|------|
| 范围 | 硬过滤真剔除 + 自选名称旁「停」 |
| 无当日停牌行 | 宽松：不剔除、`suspended=false` |
| 架构 | `suspend.py` 加载 set；`apply_hard_filters(..., suspended_vts=)` |
| UI | 名称旁小标签，非独立列 |

---

## 1. 停牌服务

新建 `backend/app/services/suspend.py`：

| 函数 | 行为 |
|------|------|
| `resolve_suspend_cal_date(db) -> str` | `latest_open_yyyymmdd` → `YYYY-MM-DD`（与 sync 写入一致） |
| `load_suspended_vt_symbols(db, cal_date: str \| None = None) -> set[str]` | 查 `app.symbol_suspend_days` 该日；`(symbol, exchange)` → `to_vt_symbol`；无行 → `set()` |

---

## 2. 硬过滤

改 `apply_hard_filters(rows, prefs, *, suspended_vts: set[str] | None = None)`：

- 当 `prefs.exclude_suspended` **且** `suspended_vts` 非空：剔除 vt（`QuoteRow.symbol` 经现有 `_to_vt_symbol` / 等价）落在集合内者  
- `suspended_vts is None` 或空 → **不**因停牌剔除  
- `exclude_suspended=false` → 不剔除  

**调用方**（`engine` / `pattern_screen` / `leader_screen` / `reference_peer`）：有 `db` 时加载 set 传入；无法取 db 时省略（默认 `None`，宽松）。

---

## 3. 自选

- `WatchlistItemOut.suspended: bool = False`  
- `GET /watchlist` enrich：当日 set 命中 → `true`  
- 前端列表名称旁：`suspended` 时 `<span class="suspend-tag" title="停牌">停</span>`  
- 详情头可选同样小标  
- 不新增表列、不进列偏好  

quotes 若走同一 `_enrich` / 同一 `WatchlistItemOut` 则自然带上；若独立结构无该字段则可不改。

---

## 4. 测试与文档

### 后端

- load：空表空 set；有行 vt 正确  
- 过滤：非空 set + exclude → 剔除；空/`None`/exclude=false → 不剔除  
- 自选 enrich：`suspended` 布尔正确  

### 工程

- smoke：同步停牌后 Hub 排除停牌生效；自选见「停」  
- 路线图 #44 链本 spec  
- `./scripts/check.sh` 绿  

## 验收

- [ ] 有停牌数据且 exclude 开 → 选股结果无当日停牌票  
- [ ] 无停牌数据 → 选股行为与改前一致（不误杀）  
- [ ] 自选停牌票名称旁「停」  
- [ ] pytest + 前端 build 绿  

## 风险

- QuoteRow 用 TickFlow 符号（`SHSE.xxx`）：过滤比较必须统一到 vt，避免格式不一致漏滤。  
- 多调用点漏传 `suspended_vts`：默认 `None` 为宽松，不致误杀，但 exclude 开关会「看似无效」——计划内逐个改 engine/pattern/leader/peer。
