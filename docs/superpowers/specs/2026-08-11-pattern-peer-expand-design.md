# 形态扩因子 + 对标扩维 + 找同类 设计

日期：2026-08-11  
状态：已批准（方案 1：同刀 A+B+C）  
范围：仅 zak2；不改 zak；不 import vnpy_*

## 目标

1. **A**：新增 2 个日 K 形态 `platform_break`、`pullback_ma20`，Hub 形态下拉自动可见。  
2. **B**：标杆对标增加 **20 日动量**、**换手接近度**，默认五维权重归一。  
3. **C**：Hub 结果行「找同类」一切换到对标 Tab、填入标杆并跑现有 API。

## 非目标

- MCP 形态扫描、改 zak 桌面  
- 配方多因子扩维、形态中文别名  
- 对标权重持久化 UI / 进度取消  
- Docker、下单、计划页

## A · 形态规则

文件：`backend/app/services/pattern_rules.py`（+ `PATTERN_META` / `PATTERN_MATCHERS`）

### `platform_break`（平台突破）

- 日 K 至少约 40 根  
- 平台窗：突破前 **15** 根（不含最新 1～2 根）：振幅 `(max high − min low) / min low ≤ 8%`  
- 突破：最新收盘 > 平台最高；量比（近 5 / 前 20）≥ **1.2**  
- `PatternMatch.score`：突破幅度% + 量比加权；`hint` 含平台振幅与量比  

### `pullback_ma20`（缩量回踩 MA20）

- 日 K 至少约 40 根；存在 MA20  
- 近 **10** 日内最低曾贴近 MA20：`|low − MA20| / MA20 ≤ 2%`  
- 「收阳」：`BarSeries` 无 open 时用 **最新收盘 ≥ 前收**  
- 近 5 日量比 ≤ **0.9**  
- 若有 MA60：要求 MA20 > MA60  
- `hint`：距 MA20% 与量比  

`theme_hot` / 既有三 matcher 不变。`pattern_screen` 无需特殊分支（走通用 K 线 matcher）。

## B · 对标五维

文件：`backend/app/services/reference_peer.py`

| 键 | 默认权重 | 计分 |
|----|----------|------|
| `industry` | 0.30 | 同业候选固定 100 |
| `valuation` | 0.25 | 现有 PE+流通市值对数距离 |
| `momentum_5d` | 0.15 | 现有 5 日累计涨跌接近度 |
| `momentum_20d` | 0.15 | 同 `momentum_score`，`_fetch_pct_maps(days=20)` |
| `turnover` | 0.15 | `100 − min(\|to_ref−to_cand\|, 20)×5`；缺换手 → 中性 50 |

- `composite_similarity` 改为五维加权；`config.weights` 写出全部键  
- 可选请求覆盖 `weights`（schema 可选 dict，缺省用上表；实现时若改 Request 须向后兼容）  
- 结果：保留 `momentum_5d`；新增 `momentum_20d`；换手分可进 `pattern_hint` / `hit_reason` 或字段 `turnover_score`  
- 单测：纯函数 score + 权重和、mock 路径不打真 Tushare  

## C · Hub「找同类」

文件：`frontend/src/views/ScreenerHubView.vue`（必要时 `screener.ts` 无新 API）

- 结果表操作列在「自选」旁增加「找同类」  
- 点击：`peerSymbol = row.vt_symbol || 由 symbol 推导` → `tab = 'peer'` → 调用与对标 Tab 相同的 `runReferencePeer` 流程  
- 不新增后端路由  

## 测试

- `test_pattern_rules.py`：两形态命中 / 不命中边界（窄平台、无突破、未贴 MA20、放量过大等）  
- `test_reference_peer.py`：换手分、20 日动量分、五维 composite；既有用例随权重更新断言  
- 前端：`npm run build`  

## 文档

- `gap-vs-desktop.md`：形态 6 种（原 4 + 2）；对标五维；Hub 可找同类  
- 「建议下一刀」：只读持仓/信号工具或其它（不绑 Docker）  
- `smoke-checklist.md`：形态下拉可见新项；对标结果含新维度文案；结果行找同类  

## 验收

1. `GET /patterns` 含 `platform_break`、`pullback_ma20`  
2. 对标 `config.weights` 五键；相关 pytest 绿  
3. Hub 找同类可切 Tab 并触发对标跑  
4. `npm run build` 绿  

## 澄清记录

- 用户选 A+B+C；默认形态名与对标权重如上  
- 实现路径：分模块同刀，权重不做用户 meta 编辑器  
