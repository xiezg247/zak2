# 通知历史（自选只读）设计

日期：2026-08-07  
状态：已批准（方案 1：独立 GET + 自选可折叠区）  
范围：仅 zak2；不改 zak / vnpy-*；共用 PG `app.notify_delivery_log`

## 目标

1. **只读通知投递历史**：当前用户最近 N 条出站记录（桌面写入的飞书等投递日志）。
2. **自选页可折叠区**：懒加载列表；行可展开查看 payload JSON。

## 非目标

- 发送通知、改订阅、删日志、限频/静默配置
- 独立路由、按 event/status 筛选、分页翻页（仅 `limit`）
- 下单、API 内异动扫描、改 zak 代码

## 数据

表：`app.notify_delivery_log`（多用户含 `user_id`）

| 列 | 用途 |
|----|------|
| id | 主键 |
| user_id | 租户过滤 |
| event_type | 事件类型 |
| channel | 渠道（如 feishu） |
| payload_json | 原文 JSON 字符串 |
| status | 投递状态 |
| error | 错误信息 |
| created_at | 创建时间（文本，桌面中国时区格式） |

查询：`WHERE user_id=:uid ORDER BY created_at DESC LIMIT :limit`

## API

### `GET /api/v1/watchlist/notify-log`

Query：

- `limit`：默认 **50**，夹逼到 **[1, 100]**

响应：

```json
{
  "items": [
    {
      "id": "...",
      "event_type": "...",
      "channel": "feishu",
      "status": "ok",
      "error": "",
      "created_at": "...",
      "payload": {}
    }
  ],
  "limit": 50,
  "count": 1
}
```

- `payload`：`json.loads(payload_json)`；失败则 `{ "_raw": "<原文>" }`
- 空表 → `items: []`
- 只读；无 POST/PUT/DELETE

实现建议：

- Service：`backend/app/services/notify_log.py`（SQLAlchemy `text` 或轻量 ORM）
- Schema：`NotifyLogItem` / `NotifyLogOut`
- Route：挂在现有 `watchlist` router

## 前端

- 文件：`frontend/src/api/watchlist.ts`、`WatchlistView.vue`
- 位置：策略看盘内、**风控卡片下方**可折叠「通知历史」
- 默认折叠；**首次展开**再 GET（懒加载）
- 列：时间 · 事件 · 渠道 · 状态 · 错误摘要
- 点击行展开 `<pre>` pretty-print `payload`
- 状态：成功类正常色；失败类沿用 `warn`/`err`
- 「刷新」重拉；错误中文提示
- 不进顶栏导航

## 错误与降级

| 情况 | 行为 |
|------|------|
| 无记录 | 空态文案 |
| limit 非法/越界 | 夹逼，不 400 |
| payload 非 JSON | `_raw` 回退 |
| DB 错误 | 500 / 前端错误提示 |

## 测试

- limit 夹逼（0→1，200→100，缺省 50）
- 空列表
- payload 合法 JSON / 非法 → `_raw`
- user_id 隔离（mock SQL 参数或两用户 fixture）
- 不打真网、不发通知

## 文档

- gap：风控通知 → 有通知历史只读；下一刀另定
- smoke：自选可展开通知历史并见条目/空态

## 验收

1. 有投递记录时可见最近条目并可展开 payload  
2. 无记录空态；limit 夹逼生效  
3. pytest + `npm run build` 绿  
