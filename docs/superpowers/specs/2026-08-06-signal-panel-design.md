# 信号名单 Web 编辑设计

日期：2026-08-06  
状态：按方案 A 实施（用户「继续」）

## 目标

Web 可编辑策略看盘「信号名单」；存 PG，看板优先按名单拉 cache。

## 存储

- 表：`auth.user_preferences`
- `namespace=watchlist`，`key=signal_panel_symbols`
- `value_json={"symbols":["600519.SSE",...]}`
- 上限 10（对齐桌面 `SIGNAL_PANEL_MAX_SYMBOLS`）
- 与桌面本地 UI 偏好不同步（产品约定：不改 zak，Web 自洽即可）

## API

- `GET/PUT /api/v1/watchlist/signal-panel`
- `POST /api/v1/watchlist/signal-panel/members`
- `DELETE /api/v1/watchlist/signal-panel/members/{vt_symbol}`

## 看板

名单非空 → 按名单顺序取 Redis/PG signal cache；空 → 保持现有「自选∩cache / scan」回退。

## UI

自选页策略看盘信号区：展示名单、从当前选中/输入加入、删除。
