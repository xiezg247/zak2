# 雷达展望加深（共振对齐 + 规则预测）设计

日期：2026-08-14  
状态：已批准（已实现）  
范围：仅 zak2；不改 zak；不做 LLM 展望；不移植桌面 horizon/predict 全量管线  
前置：`scan_horizon_outlook` 启发式闭环（#26）；`cache.radar_predict_cache` 表已存在但无写路径

## 背景

`/radar` 展望区已通：Ops `scan_horizon_outlook` → `cache.radar_horizon_cache` → `GET /radar/horizon`。算法仅为默认权重下的跨卡共振 Top30（`strategy_key=resonance_heuristic`）。

已知缺口：

- job 未传 `first_time_map`，封板标签弱于侧栏实时共振
- 漏斗字段（`excluded_count` / 去重 `scanned_total`）未如实填写
- 合成卡片覆盖窄（权重 >0 的部分卡未合成）
- `radar_predict_cache` 空表；无规则/模型预测层；UI 仅单区启发式

产品选择：**同 job 两阶段**一次交付——Phase A 加深共振快照 + Phase B 可解释规则预测写 predict cache + `/radar` 双区。LLM 文案层留后续刀。

## 目标

1. 加深 `scan_horizon_outlook` Phase A：对齐封板 map、填实漏斗元数据、能接的卡片加宽。  
2. 同 job Phase B：对 Phase A TopN 规则打分，写入 `cache.radar_predict_cache`（`model_label=rules_v1`）。  
3. 新增 `GET /api/v1/radar/predict`；RadarView 展示「共振展望」+「规则预测」两区。  
4. 失败可观测：A 成功则 job 可标 success，message 标明 predict 状态；缺 K 计入 `kline_missing`。  
5. 路线图 / smoke / catalog 文案更新。

## 非目标

- LLM 展望、`radar_ai_hint_cache`、板块 LLM cache 写入  
- job 使用用户共振权重 / `needs_user_id`  
- `watchlist_*` 卡片合成（无调度用户维度）  
- 展望行一键入自选 / 计划草案 / AI skill 读 horizon  
- 桌面全市场扫描或 import zak 管线  
- 改 zak / 交易下单

## 决策摘要

| 项 | 选择 |
|----|------|
| 落法 | 同 job 两阶段（非拆 job、非纯实时 API） |
| 权重 | 继续默认 `CARD_WEIGHTS` |
| 预测 | 纯规则 `rules_v1`（可解释 `reasons`） |
| LLM | 本轮不做 |
| UI | 一次双区交付 |

---

## 1. 架构与数据流

```
warm_radar_card_snapshots
        │
scan_horizon_outlook
  ├─ Phase A  list_radar_cards + load_first_time_map + compute_resonance
  │            → cache.radar_horizon_cache (strategy_key=resonance_heuristic)
  └─ Phase B  score_predict_rows(horizon_rows) + 日 K 存在性批量查
               → cache.radar_predict_cache (model_label=rules_v1)
        │
GET /radar/horizon（已有）
GET /radar/predict（新）
        │
RadarView：共振展望 | 规则预测
```

| 组件 | 职责 |
|------|------|
| Ops / ARQ | 仍注册 `scan_horizon_outlook`；catalog 改为「共振启发式 + 规则预测」 |
| Phase A | 默认权重；`min_cards=2`，`top_n=30`；传 `first_time_map` |
| Phase B | 纯函数打分；upsert predict；异常不回滚已写 horizon |
| API | horizon 保持；predict 镜像读路径 |
| UI | 双折叠表 + Ops 引导 |

---

## 2. Phase A：启发式加深

### 2.1 共振调用

```text
cards = list_radar_cards(db)
ft = load_first_time_map(db)
resonance = compute_resonance(cards, min_cards=2, top_n=30, first_time_map=ft)
```

### 2.2 漏斗元数据

| 字段 | 含义 |
|------|------|
| `scanned_total` | 卡片内有效去重 `vt_symbol` 数 |
| `excluded_count` | 去重后未达 `min_cards` 的标的数 |
| `prefilter_total` | 本轮 = `scanned_total`（无独立 K 预筛） |
| `refined_total` | `len(rows)` |
| `kline_missing` | Phase A 写 **0**（K 检查在 Phase B） |

### 2.3 卡片加宽

在 `build_synthesized_cards` 中**必须**新增两张合成卡（无数据则返回空 `rows` 的卡仍可省略整张卡，避免权重污染——即：有 ≥1 行才 append）：

| card_id | 数据源 | 规则 |
|---------|--------|------|
| `discovery_limit_break` | 当日涨停列表（与 ladder 同源） | `open_times > 0` 的标的，按开板次数降序，最多 30 行 |
| `discovery_volume_surge` | Redis 行情排行 / quote 字段 | `volume_ratio` 降序 Top30（阈值：`volume_ratio ≥ 2`；无排行则整卡省略） |

`watchlist_short_term` / `watchlist_intraday`：**不做**（需用户）。

`priority` 排序表同步纳入新 card_id。

---

## 3. Phase B：规则预测

### 3.1 候选集

Phase A 产出的 `rows`（已截断 Top30）。若 A 为空，predict 写空行并 `refined_total=0`。

### 3.2 打分（`predict_score` + `reasons[]`）

| 因子 | 分 | 条件 | reason 示例 |
|------|----|------|-------------|
| 共振底座 | `+resonance_score` | 始终 | `共振 {score}` |
| 多卡加成 | `+0.5` / `+1.0` | `card_count≥3` / `≥4` | `出现≥3卡` |
| 涨幅档 | `+0.8` / `+0.4` / `0` / `−0.5` | `change_pct≥7` / `≥3` / 有值且 &lt;3 / `&lt;0`；缺失不加不减 | `涨幅≥7%` |
| 封板标签 | `+0.6` | `seal_time_label` 非空 | `有封板时刻` |
| 日 K 可用 | `+0.3` | 该 vt 近 5 根 `interval=d` 存在；否则累计 `kline_missing` | `近5日K可用` |

排序：`(-predict_score, -resonance_score, vt_symbol)`，截断 30。

### 3.3 写入 `radar_predict_cache`

| 列 | 值 |
|----|-----|
| `variant` | `default` |
| `model_label` | `rules_v1` |
| `rows_json` | 行：horizon 字段 + `predict_score` + `reasons` |
| `scanned_total` | 候选行数（Phase A refined） |
| `excluded_count` | 0（本轮无第二层剔除；若未来加阈值再填） |
| `prefilter_total` | 同 scanned |
| `refined_total` | 写出行数 |
| `kline_missing` | 缺近 5 日 K 的行数 |
| `computed_at` | UTC ISO |

日 K 存在性：批量查 `public.dbbardata`（按 symbol/exchange 解析自 vt），避免逐行 N+1。

---

## 4. API 与 Schema

### 4.1 `GET /api/v1/radar/predict`

- 鉴权：与 horizon 相同（登录用户）  
- 响应 `RadarPredictOut`：

```text
variant, model_label, computed_at, scanned_total, refined_total, kline_missing,
rows: [{ vt_symbol, name, predict_score, resonance_score, card_count, card_titles,
         change_pct, last_price, seal_time_label, reasons }],
empty, label="规则预测（共振+可解释加分）"
```

- 无 cache 行：`empty=true`，200（与 horizon 一致）

### 4.2 Horizon

保持现契约；Phase A 写入后 `excluded_count` 若读 API 未暴露，可不扩 GET（YAGNI）；落库必须正确。

---

## 5. UI（`RadarView.vue`）

| 区 | 行为 |
|----|------|
| 共振展望 | 原「展望」改名；文案仍标明启发式 |
| 规则预测 | 新折叠区；列：预测分、理由、共振分、涨跌%、封板、名称 |
| 空态 | 两区皆无 → 引导 `scan_horizon_outlook`（需先 warm 卡片） |
| 偏斜空态 | horizon 有、predict 无 → 「上次预测阶段失败或未写入，可于 Ops 重跑」 |

并行拉取：`radarHorizon()` + `radarPredict()`；互不影响失败。

---

## 6. Job 返回与失败

| 情况 | `success` | 行为 |
|------|-----------|------|
| A+B 皆成功 | `true` | message 含 horizon/predict 行数 |
| 无卡片 | `true` | 两表可写空；message 引导 warm |
| A 成功、B 异常 | `true` | **commit horizon**；predict 不更新或显式不写；message 含 `predict_error=...` |
| A 异常 | `false` | 不保证更新任一 cache |

不因单票缺 K 失败整 job。

---

## 7. 模块边界

| 路径 | 变更 |
|------|------|
| `ops_scan_horizon_outlook.py` | 两阶段；漏斗；调用 predict 打分/upsert |
| `radar_predict.py`（新）或 `radar_horizon_predict.py` | `score_predict_rows`、`load_predict`、`upsert_predict` |
| `radar.py` | 合成 `discovery_limit_break` / `discovery_volume_surge` |
| `schemas/market.py` | `RadarPredictRow` / `RadarPredictOut` |
| `api/v1/market.py` | `GET /radar/predict` |
| `ops_catalog.py` / scheduler 描述 | 文案 |
| `frontend/.../RadarView.vue` + `api/market.ts` | 双区 |
| 测试 | Phase A map/漏斗；规则分表驱动；predict API 空/有数据；job A 成功 B 失败仍 success |

---

## 8. 验收

- [ ] 有卡片时跑 job → horizon + predict 均有 `computed_at`  
- [ ] predict 分与 `reasons` 符合 §3.2；缺 K 反映 `kline_missing`  
- [ ] `/radar` 双区可读；空态 Ops 引导正确  
- [ ] A 成功 B 失败：horizon 仍可读，message 含 predict_error  
- [ ] `./scripts/check.sh` 绿  
- [ ] 路线图 #52 + smoke 更新  

## 风险

| 风险 | 缓解 |
|------|------|
| 规则分启发式噪音 | UI 标明「规则预测」；固定 `rules_v1` 可迭代 |
| 合成卡无数据 | 整卡省略，不写空壳卡 |
| job 变慢（批量日 K） | 仅 Top30；单次 IN 查询 |
| 与侧栏权重不一致 | 文档/文案：展望用默认权重 |

## 后续刀（非本范围）

- LLM 短评（原选项 C）  
- 用户权重进 job / 多 variant  
- 展望行操作、AI 读 predict  
- 真·桌面扫描管线
