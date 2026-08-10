# 形态选股加深（老鸭头 + 主题投资）

日期：2026-08-06  
状态：已批准并实现（方案 C）

## 增量

- `old_duck`：日 K 规则，对齐桌面简化老鸭头
- `theme_hot`：仅 Redis；涨幅≥2% 且换手≥3%；score=换手×涨幅

仍走 `POST /screener/runs/pattern` 与 Hub「形态」下拉。
