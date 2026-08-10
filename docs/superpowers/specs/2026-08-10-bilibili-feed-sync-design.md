# B 站信息流 Web 同步设计

日期：2026-08-10  
状态：已批准（方案 A：zak2 精简移植；只同步已有订阅）  
范围：仅 zak2；不改 zak / 不 import vnpy_*

## 目标

1. zak2 自实现 B 站动态拉取（Cookie + WBI），同步已启用的 `bilibili_up` 订阅并 upsert `feed_items`。  
2. `sync_bilibili_feed` 进入 `RUNNABLE` + 默认定时；Ops 可手动执行。  
3. 无 Cookie / 无启用订阅 → job skipped（成功态文案）。

## 非目标

- 新增 / 删除 UP 订阅（另刀）  
- import `vnpy_ashare` / 改 zak  
- 新条目通知推送  
- feed_cursor 表（本刀靠 `external_id` 去重）  
- 无 Cookie 强拉公开接口  

## 配置

`Settings.bilibili_cookies: str = ""`（环境变量 `BILIBILI_COOKIES`）。  
`.env.example` 增加说明（Cookie 字符串，与桌面同源即可）。

## 模块

```text
backend/app/integrations/bilibili/
  client.py      # Cookie + WBI 签名 + GET（精简移植桌面逻辑，不 import vnpy）
  dynamics.py    # list_recent_dynamics(mid, count)
  normalize.py   # raw → FeedItemDraft(title, summary, url, external_id, published_at, item_type, payload)
backend/app/services/ops_sync_bilibili_feed.py
  sync_bilibili_feed(db) -> dict  # success/skipped/message/new_items/...
```

## 同步语义

1. 未配置 Cookie → `{success: True, skipped: True, message: "未配置 BILIBILI_COOKIES…"}`  
2. 查询 `feed_subscriptions`：`enabled=1` 且 `source_type=bilibili_up`（**跨用户**）  
3. 无订阅 → skipped  
4. 对每个订阅：拉近期动态 → normalize → 已存在 `(subscription_id, external_id)` 跳过 → 否则 INSERT `feed_items`  
5. 订阅间 sleep（约 2–3s）限流  
6. 非强制且非 08:00–20:00（中国时区）→ skipped（手动 Ops force 可绕过；定时走窗口）  
7. `save_job_run_meta` 记录结果  

`item.id`：uuid4 字符串。`published_at` / `created_at`：ISO 文本。

## Ops / 调度

- `ops_catalog.RUNNABLE_JOB_IDS` 加入 `sync_bilibili_feed`  
- `ops_runners.RUNNERS` 映射  
- `scheduler_defaults.DEFAULT_CRON`：工作日 8–19 点每小时（或等价）；与桌面窗口对齐意图  
- JobSpec 描述改为 Web 可跑（不再「仅 CLI」）  

## UI / 文案

- `FeedView.vue`：同步可由 Ops / 定时；不再写死「仅 CLI」  
- `OpsView.vue`：若有 CLI-only 特例列表，纳入可跑提示  

## 测试

- normalize：样例 raw → 字段  
- sync：mock client；无 Cookie skip；无订阅 skip；新 item 插入 / 重复跳过  
- catalog：job ∈ RUNNABLE；runner 键齐  
- 不打真 B 站  

## 文档

- `gap-vs-desktop.md`：信息流 Web 可同步；建议下一刀添加 UP / Docker  
- `smoke-checklist.md`：Ops 跑 `sync_bilibili_feed`；Cookie 后 feed 可见新条目  
- README（若有 env 表）+ `.env.example`  

## 验收

1. mock 下有 Cookie + 订阅 → 可插入新 items  
2. 无 Cookie / 无订阅 → skipped  
3. `sync_bilibili_feed` ∈ RUNNABLE；相关 pytest 绿  
