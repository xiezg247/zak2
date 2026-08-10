# 策略看盘持仓风险 Tag（薄）设计

日期：2026-08-07  
状态：已批准（方案 1：纯函数 + strategy_board 注入）  
范围：仅 zak2；不改 zak / vnpy-*

## 目标

- 策略看盘「持仓区」每行增加只读风险标签：`浮亏` / `浮盈` / `急跌` / `大涨` / `放量`，以及已有卖出语义对应的「卖出信号」。
- 纯函数计算（Redis 行情字段 + 已有浮亏%）；无 TickFlow、无通知扫描、不改持仓 CRUD。

## 非目标

- 计划外、开盘止损、上午必卖、浮亏扛单
- `trading/risk` 偏好 UI、通知收件箱、飞书出站
- 下单 / OMS、API 内跑策略
- 持仓 CRUD 表另挂一列（本刀仅策略看盘）

## 纯函数

文件：`backend/app/services/position_risk_tags.py`

```text
compute_position_risk_tags(
  *,
  exit_signal: str | None,
  unrealized_pnl_pct: float | None,
  change_pct: float | None,
  volume_ratio: float | None,
) -> list[str]
```

可选：`primary_risk_tag(tags) -> str | None`（取列表首项）。

### 阈值（写死，对齐桌面轻量子集）

| Tag | 条件 |
|-----|------|
| 卖出信号 | `exit_signal == "sell"` |
| 急跌 | `change_pct ≤ -3` |
| 大涨 | `change_pct ≥ 5` |
| 放量 | `volume_ratio ≥ 1.2` 且 `|change_pct| ≥ 1.5` |
| 浮亏 | `unrealized_pnl_pct ≤ -5` |
| 浮盈 | `unrealized_pnl_pct ≥ 15` |

### 排序（严重度，写死）

`卖出信号` > `急跌` > `浮亏` > `放量` > `大涨` > `浮盈`

同批命中按上述顺序输出；缺字段则跳过依赖该字段的 tag，不抛错。

## 接入

- `strategy_board` 组装持仓行时调用纯函数，写入：
  - `risk_tags: list[str]`
  - `risk_primary: str`（空串表示无）
- 沿用现有 `GET /api/v1/watchlist/strategy-board`；**无新路由**
- OpenAPI / TS 类型同步字段

## 前端

- `WatchlistView` 策略看盘持仓区增加「风险」列
- 展示 `risk_tags`（短文本或轻量芯片）；无 tag 显示「—」
- 不改持仓 CRUD 区

## 错误与降级

| 情况 | 行为 |
|------|------|
| 无 last / 无 pnl% / 无 quote | 跳过相关 tag |
| Redis 不可用 | 策略看盘现有降级；风险列多为空 |
| 不写库、不发通知 | — |

## 测试

- 纯函数：各 tag 命中/不命中、排序、缺字段
- strategy_board：mock quote 后持仓行含 `risk_tags`
- 不打真网

## 文档

- `docs/gap-vs-desktop.md`：风控/交易链路 → **薄**（策略看盘只读 risk tag）；下一刀可写计划外 / risk 偏好等
- `docs/smoke-checklist.md`：自选策略看盘可见风险列

## 验收

1. 浮亏≤−5% 时出现「浮亏」  
2. `exit_signal=sell` 时出现「卖出信号」  
3. 全量 pytest + `npm run build` 绿  
