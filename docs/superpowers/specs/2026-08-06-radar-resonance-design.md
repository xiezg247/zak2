# 雷达共振侧栏（薄）设计

日期：2026-08-06  
状态：已批准（方案 A）

## API

`GET /api/v1/radar/resonance?top_n=20&min_cards=2`

跨卡计数 + 固定权重；标的须有 `vt_symbol`（或可从 `tf_symbol` 推导）。

## 前端

雷达页右侧可折叠侧栏：Top 列表、加自选、龙头选股→Hub。

## 非目标

权重 UI、封板时间、Hub 雷达共振配方。
