# 标杆对标设计

日期：2026-08-06  
状态：已批准（方案 B，Tushare 对齐桌面）

## API

`POST /api/v1/screener/runs/reference-peer`  
`{ "vt_symbol": "600519.SSE", "top_n": 20, "hard_filter_template": "balanced" }`

异步 job，结果写入 `screener_runs`。

## 打分

同业 40% + 估值接近 35% + 近 5 日动量 25%（与桌面一致）。

## 非目标

无 token 假数据、改 zak。
