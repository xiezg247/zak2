# 信息流添加/删除 UP 设计

日期：2026-08-10  
状态：已批准（方案 A：mid + profile；Feed 表单；含删除）  
范围：仅 zak2；不改 zak；不 import vnpy_*

## 目标

1. 当前用户可按 B 站 **mid** 添加 `bilibili_up` 订阅；可选 `sync_now` 立即同步该订阅。  
2. 可删除本人订阅（并清理该订阅下 `feed_items`）。  
3. Feed 页：mid 输入 + 添加（及可选同步）；侧栏删除。

## 非目标

- 关键词搜索 UP  
- 改全局 `sync_bilibili_feed` 语义（仅复用单订阅同步）  
- 改 zak / 通知  

## API

### `POST /api/v1/feed/subscriptions`

Body:

```json
{ "mid": "123456", "sync_now": false }
```

- 需已配置 `BILIBILI_COOKIES`，否则 400  
- `mid` 非空数字串（strip）  
- 同用户已存在同 `source_id` → 400「已订阅」  
- 同用户订阅数 ≥ 50 → 400「达上限」  
- `get_user_profile` 失败：仍创建；`display_name=mid`，`avatar_url=""`  
- `sync_now=true`：同步该订阅；失败时订阅仍保留，HTTP 200；`FeedSubOut.sync_error?: string` 供前端提示  

### `DELETE /api/v1/feed/subscriptions/{sub_id}`

- 非本人 → 404  
- `DELETE FROM feed_items WHERE subscription_id=…` 再删 subscription  
- 返回 `{ok: true}`

## 模块

| 路径 | 职责 |
|------|------|
| `integrations/bilibili/user.py` | `get_user_profile` |
| `services/feed.py` | `add_bilibili_up` / `delete_subscription` |
| `services/ops_sync_bilibili_feed.py` | 导出 `_sync_one_subscription`（或公开 `sync_subscription`）供 add 复用 |
| `api/v1/content.py` | POST/DELETE |
| `schemas/content.py` | `FeedSubCreate`；`FeedSubOut.sync_error` 可选 |
| `frontend` FeedView + content API | UI |

常量：`MAX_FEED_SUBSCRIPTIONS = 50`（每用户）。

## 测试

- profile mock；add 成功 / 重复 / 上限 / 无 Cookie  
- delete：items + sub 清除；跨用户 404  
- sync_now mock 成功/失败  
- 不打真站  

## 文档

- gap：可添加/删除 UP；建议下一刀关键词搜索 / Docker  
- smoke：Feed mid 添加、删除、可选同步  

## 验收

1. mid 添加成功；重复/超限/无 Cookie 有明确错误  
2. 删除后订阅与 items 消失  
3. Feed UI + pytest + `npm run build` 绿  
