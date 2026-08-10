# 信息流关键词搜索 UP 设计

日期：2026-08-10  
状态：已批准（方案 A：独立搜索 API + Feed 结果列表点选添加）  
范围：仅 zak2；不改 zak；不 import vnpy_*

## 目标

1. 按关键词搜索 B 站 UP（WBI `search/type`）。  
2. Feed 展示候选列表；点选后走现有 `POST /feed/subscriptions`（可 `sync_now`）。  
3. 保留 mid 直填添加。

## 非目标

- 关键词盲加第一条  
- 改添加/删除/同步 job 语义  
- 改 zak  

## API

`GET /api/v1/feed/bilibili/search`

| 参数 | 说明 |
|------|------|
| `q` | 关键词（必填 query；空则返回空列表） |
| `limit` | 默认 8，夹在 1–20 |

需 `BILIBILI_COOKIES`，否则 400「未配置 BILIBILI_COOKIES」。

响应：

```json
{
  "results": [
    { "mid": "123", "name": "UP名", "avatar": "https://...", "sign": "签名" }
  ]
}
```

## 模块

| 路径 | 职责 |
|------|------|
| `integrations/bilibili/user.py` | 增 `search_users(client, keyword, limit=)`（精简移植桌面） |
| `services/feed.py` | `search_bilibili_ups(q, limit)`：Cookie 校验 + 调 search_users |
| `schemas/content.py` | `BilibiliUserHit` / `BilibiliSearchOut` |
| `api/v1/content.py` | `GET /feed/bilibili/search` |
| `FeedView.vue` + `content.ts` | 搜索 UI + 点选添加 |

搜索路径：`/x/web-interface/wbi/search/type`，`search_type=bili_user`，`signed=True`。

## 前端

- 搜索输入 +「搜索」按钮（可与 mid 区并列或共用输入：数字倾向 mid 添加，非数字可提示先搜索——**本刀**：独立「关键词」输入 + 搜索，避免与 mid 混淆）  
- 结果列表：名称、mid、可选头像；行按钮「添加」（沿用 `syncOnAdd`）  
- 空结果 / 错误文案  

## 测试

- `_normalize_search_user` / `search_users` mock client 返回  
- 无 Cookie → 400；空 q → `{results:[]}`  
- 不打真站  

## 文档

- gap：可关键词搜索 UP；建议下一刀 Docker 等  
- smoke：Feed 搜索 → 点选添加  

## 验收

1. mock 搜索结果正确归一化  
2. 点选走现有添加路径  
3. 相关 pytest + `npm run build` 绿  
