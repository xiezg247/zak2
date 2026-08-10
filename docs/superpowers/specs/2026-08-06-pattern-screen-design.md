# 形态选股子集设计

日期：2026-08-06  
状态：已批准（方案 1；宇宙 A；形态 ma_bull + w_bottom）

## 目标

在 zak2 选股 Hub 增加形态选股：`ma_bull`（均线多头）、`w_bottom`（W 底）。规则在 zak2 重写，对齐桌面公式语义，不 import `vnpy_*`。

## API

`POST /api/v1/screener/pattern`

```json
{
  "pattern_id": "ma_bull",
  "top_n": 20,
  "max_scan": 800,
  "persist": true
}
```

- `pattern_id`: `ma_bull` | `w_bottom`（必填）
- `top_n`: 默认 20，上限 100
- `max_scan`: 默认 800，上限 1200
- `persist`: 默认 true，写入 `screener_runs`（与条件选股一致）

响应：与现有 screener run 结果同形（rows + condition + total_scanned + source=`bar`），行含 `pattern_score`、`pattern_hint`。

另：`GET /api/v1/screener/patterns` 列出可用形态元数据（id/name/description）。

## 宇宙与数据

1. 从 Redis 行情池取报价行（复用条件选股同源）
2. 截断至 `max_scan`
3. 对每只票从 PG `dbbardata` 取日 K 尾部（≥60 根才参与匹配）
4. 无 K 线则跳过（计入 scanned 分母时：仅成功加载且 bars≥60 的记 scanned）

## 规则（摘要）

### ma_bull / w_bottom / old_duck / theme_hot

见加深说明：`2026-08-06-pattern-deepen-design.md`。本 spec 初版仅 ma_bull + w_bottom；后续已补齐四形态。

### ma_bull

- MA5 > MA10 > MA20 > MA60，且收盘 ≥ MA20
- score ≈ 20 日涨幅% + (MA5−MA60)/MA60×100 + min(量比, 3)×2
- hint：说明均线关系与 20 日涨幅

### w_bottom

- 近 60 日 lows 找局部低点；两底间隔 ≥8；双底高度接近；近端突破颈线（简化，对齐桌面 `match_w_bottom`）
- score / hint 对齐桌面量级

## 前端

选股 Hub：「形态」区两个按钮（均线多头 / W 底）→ 调 pattern API → 结果进现有结果表（展示 score/hint 列若已有扩展位则用，否则放 reason/备注列）。

## 非目标

- 老鸭头、主题投资、MCP 形态
- 标杆对标、多因子权重编辑
- 修改 zak 桌面代码

## 测试

- 纯函数：给定 closes/highs/lows/volumes 序列断言匹配/不匹配
- API/服务：mock Redis + bars，断言 top_n 与 pattern_id 过滤
