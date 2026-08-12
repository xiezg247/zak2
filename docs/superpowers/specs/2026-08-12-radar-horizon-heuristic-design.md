# 雷达展望启发式写读闭环设计

日期：2026-08-12  
状态：已批准（方案 A：共振启发式写 `radar_horizon_cache` + GET + 雷达页读；不做 predict）  
范围：仅 zak2；不改 zak / vnpy-*；不实现桌面全量展望扫描

## 背景

`scan_horizon_outlook` 为恒 skipped 壳；PG 有 `cache.radar_horizon_cache` / `radar_predict_cache`；雷达页仅有「暂不可用」薄壳。需要最小可感闭环：Ops 真写 → API 可读 → Web 可展示，并诚实标明非桌面全量管线。

## 目标

1. 做实 `scan_horizon_outlook`：基于现有雷达卡片共振启发式写入 `radar_horizon_cache`（`variant=default`）。  
2. 新增 `GET /api/v1/radar/horizon` 读 cache。  
3. 雷达页展望区展示结果或引导 Ops；标注「启发式展望（基于共振）」。  
4. **不**写 `radar_predict_cache`；不再恒 skipped。

## 非目标

- 桌面 horizon/predict 全量扫描或移植 zak 管线  
- 写入 predict cache  
- 改共振权重编辑 / 卡片合成算法  
- `needs_user_id`（本刀用默认权重，不绑调度用户）

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：共振启发式 → horizon cache |
| 权重 | 默认 `CARD_WEIGHTS`（无用户覆盖） |
| 空结果 | success + 空 rows（非 skipped） |
| predict | 本刀不做 |

---

## 1. Job：`scan_horizon_outlook`

### 1.1 算法

1. `cards = list_radar_cards(db)`  
2. `resonance = compute_resonance(cards, min_cards=2, top_n=30, weights=默认)`（可复用 `radar_resonance.compute_resonance`；`first_time_map` 可选加载以带封板标签）  
3. 将 `entries` 序列化为 `rows_json` 数组，每行至少含：

```json
{
  "vt_symbol": "...",
  "name": "...",
  "resonance_score": 0,
  "card_count": 0,
  "card_titles": [],
  "change_pct": null,
  "last_price": null,
  "seal_time_label": ""
}
```

4. upsert：

| 列 | 值 |
|----|-----|
| `variant` | `"default"` |
| `rows_json` | JSON 数组字符串 |
| `scanned_total` | 卡片行/去重标的近似计数（可用参与聚合前的标的数或 `len(cards)` 相关；实现时取合理值并单测固定） |
| `excluded_count` | 0 或未达 `min_cards` 丢弃数（可选） |
| `prefilter_total` / `refined_total` | 可用 `len(entries)` 填 refined；其余可 0 |
| `kline_missing` | 0 |
| `strategy_key` | `"resonance_heuristic"` |
| `computed_at` | UTC ISO |

5. `save_job_run_meta(..., last_success=True, last_message=含写入条数)`  
6. 返回 `{success: True, skipped: False, message, written: N, strategy_key}`  

无卡片或无共振条目：仍写入空数组 + success；message 说明「无共振标的」之类。

### 1.2 模块

| 路径 | 职责 |
|------|------|
| `backend/app/services/ops_scan_horizon_outlook.py` | 真写逻辑（替换 skipped 壳） |
| `backend/tests/test_ops_scan_horizon_outlook.py` | 成功写入 / 空结果 / meta |

---

## 2. 读 API

### 2.1 `GET /api/v1/radar/horizon`

- Auth：当前用户（与其它 radar 路由一致）  
- 读 `variant=default` 一行  
- 响应 schema 建议：

```typescript
{
  variant: string
  strategy_key: string
  computed_at: string | null
  scanned_total: number
  refined_total: number
  rows: HorizonRow[]
  empty: boolean  // !rows.length
  label: string   // 如「启发式展望（基于共振）」
}
```

- 从未写入：`computed_at=null`，`rows=[]`，`empty=true`（**200**，不 404）

### 2.2 模块

| 路径 | 职责 |
|------|------|
| `backend/app/services/radar_horizon.py`（新建） | load cache |
| `backend/app/schemas/market.py` | Out 模型 |
| `backend/app/api/v1/market.py` | 路由 |
| `frontend/src/api/market.ts` | `radarHorizon()` |
| 测试 | 空库 / 有行 |

---

## 3. 前端 `RadarView`

- 挂载/刷新时拉 `radarHorizon()`（与 cards 一并或其后）  
- **有 `computed_at`：** 标题「展望」；副标 `label` 或「启发式」；展开列表（代码/名称/共振分/卡数等）；显示 `computed_at`  
- **无数据：** 保留去 Ops 提示，文案改为可跑 `scan_horizon_outlook` 生成启发式展望（不再写「恒 skipped」）  
- 不改卡片网格 / 共振侧栏 / 权重 / 草案

---

## 4. 文档

- smoke：Ops 跑 outlook 非 skipped；`/radar` 展望可读或空态引导  
- roadmap：新条目标记完成并链本 spec  

---

## 5. 验收

1. 手动/单测：job 写入 `radar_horizon_cache`，`skipped is False`。  
2. `GET /radar/horizon` 返回写入行。  
3. `/radar` 展望区展示或引导 Ops（文案无「恒 skipped」）。  
4. `./scripts/check.sh` 绿。

## 6. 风险

- 启发式 ≠ 桌面展望——UI 必须标注，避免误解。  
- 依赖雷达卡片质量；无卡时只有空结果——需先 `warm_radar_card_snapshots`（文档/空态可一句带过）。
