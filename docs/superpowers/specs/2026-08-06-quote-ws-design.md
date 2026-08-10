# WebSocket 行情通知设计

日期：2026-08-06  
状态：已批准（方案 A）

## 目标

Redis `zak:notify:quotes` → FastAPI WebSocket 推 `{type, seq}` → 前端拉 REST。不推完整报价。

## 端点

`WS /api/v1/ws/quotes?token=<JWT>`

事件：
- `hello`：连接成功
- `quotes_updated`：`seq` 更新
- `ping`：可选心跳

## 前端

自选 / 市场：订阅后触发刷新；WS 通时轮询降频（如 60s）；断线恢复 15s 轮询。

## 非目标

Tick 推送、五档、改 zak 采集。
