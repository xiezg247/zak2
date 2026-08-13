# 自选详情基本面（财报 + 披露）UX 设计

日期：2026-08-13  
状态：已批准（方案 1：专用 fundamentals 读 API + 详情折叠卡片）  
范围：仅 zak2；只读展示已有 `financial_*` / `disclosure_calendar`；不改 Ops job；不下单

## 背景

Ops 已可跑 `sync_watchlist_financials`、`sync_disclosure_calendar` 写入 PG，自选详情无读路径，盘前无法用已同步数据。

## 目标

1. 自选选中标的详情展示**最近 1 期**财报关键字段 + **最近 1～3 条**披露记录。  
2. 空态分别引导去 Ops 同步对应 job。  
3. 更新 smoke 与路线图。

## 非目标

- 列表扩列 / 即将披露角标  
- 多期对比表、原始三表 JSON、`fina_indicator`  
- 自动触发 Ops job、改 sync runner  
- 并入 strategy-board  

## 决策摘要

| 项 | 选择 |
|----|------|
| 入口 | 自选详情折叠「基本面」卡片（默认展开） |
| 财报深度 | 最近 1 期 snapshot 关键字段 |
| 披露 | 最近 3 条 + 空态去 Ops |
| 架构 | 专用 `GET …/fundamentals` |

---

## 1. API

`GET /api/v1/watchlist/items/{vt_symbol}/fundamentals`（登录）

- 解析：`parse_flexible_symbol` → `to_ts_code`；非法 → 400 中文。  
- **不**要求标的已在自选。  

### 响应

| 字段 | 说明 |
|------|------|
| `vt_symbol` / `ts_code` | 规范化 |
| `snapshot` | 最新 1 行 `financial_snapshots` 或 `null`：`end_date`、`revenue`、`net_income`、`revenue_yoy`、`net_income_yoy`、`roe`、`debt_ratio`（均可 null） |
| `sync` | `financial_sync_meta` 一行或 `null`：`last_sync_at`、`latest_end_date`、`periods_count`、`sync_status`、`error_message` |
| `disclosures` | 同 `ts_code` 最多 3 条，`end_date DESC`：`end_date`、`pre_date`、`ann_date`、`actual_date` |

全空合法：`snapshot=null`、`sync=null`、`disclosures=[]`。

### 服务

新建 `backend/app/services/fundamentals.py`：`get_fundamentals(db, vt_symbol) -> dict`。  
路由挂 `backend/app/api/v1/watchlist.py`；schema 放 `schemas/watchlist.py`。

---

## 2. 前端

`WatchlistView` 右侧：日 K 迷你表**下方**增加「基本面」卡片。

| 状态 | UI |
|------|-----|
| 加载 | 「加载基本面…」 |
| 错 | `err` + detail |
| 有 snapshot | 期末 + 营收/净利（可读单位可选简化）+ 营收同比%/净利同比%/ROE%/资产负债率%；旁注 sync 时间 |
| 无 snapshot | 「暂无财报」+ `RouterLink`「去 Ops」同步自选财报 |
| 有 disclosures | 最多 3 行表：报告期 / 预告 / 公告 / 实际 |
| 无 disclosures | 「暂无披露日历」+ 去 Ops 同步披露计划 |

- `selected` 变化时请求；无 selected 不请求、不展示卡片主体。  
- 同比/比率：有值则 ×100 显示一位小数 + `%`；null → `—`。  
- `frontend/src/api/watchlist.ts`：`fundamentals(vt)`。  

不改列表列、strategy-board、持仓/风控卡片逻辑。

---

## 3. 测试与文档

### 后端

- 非法 vt → 400  
- 空库 → 200 空结构  
- mock 有 snapshot / disclosure → 字段与条数（≤3、降序）正确  

### 工程

- smoke：选中自选见基本面；空态 Ops 链可读  
- `./scripts/check.sh` 绿  
- 路线图增完成项并链本 spec  

## 验收

- [ ] 有同步数据时详情可见财报要点与披露行  
- [ ] 无数据时空态文案与 Ops 链正确  
- [ ] 切换标的重新加载  
- [ ] pytest + 前端 build 绿  

## 风险

- snapshot 金额单位为大数字：UI 可用「亿」粗格式或原样 + 科学感 mono，避免误解为股价。建议营收/净利 ≥1e8 时显示为 `x.xx 亿`。  
- 披露日字段多为 `YYYYMMDD`：展示时格式化为 `YYYY-MM-DD`（空串仍 `—`）。
