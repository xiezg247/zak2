# 信息流添加/删除 UP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 按 mid 添加/删除 B 站 UP 订阅；Feed 表单；可选添加后立即同步。

**Architecture:** `get_user_profile` + `feed.add_bilibili_up` / `delete_subscription`；复用 `ops_sync_bilibili_feed._sync_one_subscription`（导出为公开函数）；content API + FeedView。

**Tech Stack:** FastAPI、httpx bilibili client、Vue FeedView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-feed-add-up-design.md`

## Global Constraints

- 只改 zak2；不改 zak；不 import vnpy_*
- 不做关键词搜索
- Commit 仅用户明确要求时（默认跳过）
- 不打真 B 站

**Clarifications:**

- `MAX_FEED_SUBSCRIPTIONS = 50`（每用户）
- profile 失败仍创建（name=mid）
- `sync_now` 失败：订阅保留，200 + `sync_error`
- 删除：先删 `feed_items`（及可选 `feed_item_reads` 经 item），再删 subscription
- DB 若有全局 `UNIQUE(source_type, source_id)`：同 mid 第二用户可能 IntegrityError → 转 400「该 UP 已被订阅」

---

## File map

| 文件 | 职责 |
|------|------|
| `integrations/bilibili/user.py` | **新建** get_user_profile |
| `services/ops_sync_bilibili_feed.py` | 导出 `sync_one_subscription` |
| `services/feed.py` | add / delete |
| `schemas/content.py` | FeedSubCreate；FeedSubOut.sync_error |
| `api/v1/content.py` | POST/DELETE |
| `tests/test_feed_subscriptions.py` | **新建** |
| `frontend/src/api/content.ts` / `FeedView.vue` | UI |
| docs / smoke / gap | 文档 |

---

### Task 1: profile + feed add/delete + API

**Files:**
- Create: `backend/app/integrations/bilibili/user.py`
- Modify: `ops_sync_bilibili_feed.py`（`sync_one_subscription = _sync_one_subscription` 或 rename 公开）
- Modify: `feed.py`、`schemas/content.py`、`content.py` API
- Create: `backend/tests/test_feed_subscriptions.py`

**Interfaces:**
```python
# user.py
def get_user_profile(client: BilibiliClient, mid: str) -> dict[str, str]:
    # GET /x/space/acc/info?mid=  signed=False → {mid, name, avatar, sign}

# feed.py
MAX_FEED_SUBSCRIPTIONS = 50

def add_bilibili_up(db, user_id, mid: str, *, sync_now: bool = False) -> FeedSubOut: ...
def delete_subscription(db, user_id, sub_id: str) -> None: ...
```

- [ ] **Step 1: 写失败单测（mock）**

```python
# test_feed_subscriptions.py
def test_add_requires_cookies(monkeypatch): ...
def test_add_duplicate(monkeypatch): ...
def test_add_success(monkeypatch): ...
def test_delete_removes_items(monkeypatch): ...
```

用 MagicMock db + patch get_settings / get_user_profile / sync_one。

- [ ] **Step 2: 实现 user.py + feed add/delete + schema/API**

`add_bilibili_up` 要点：
1. cookies 空 → HTTPException 400  
2. mid strip；空 → 400  
3. count user subs ≥ 50 → 400  
4. 已存在同 user + bilibili_up + mid → 400  
5. profile try/except  
6. INSERT FeedSubscription（uuid id，enabled=1，config_json=`{"dynamics": true}` 或 `{}`）  
7. sync_now → `sync_one_subscription`；异常 → `sync_error=str(exc)`  
8. commit；返回 FeedSubOut  

`delete_subscription`：校验归属；delete items where subscription_id；delete reads for those items if needed；delete sub；commit。

- [ ] **Step 3: 跑测绿**

```bash
cd backend && python -m pytest tests/test_feed_subscriptions.py -v
```

- [ ] **Step 4: Commit（仅用户要求时）**

---

### Task 2: Feed UI

**Files:**
- Modify: `frontend/src/api/content.ts`
- Modify: `frontend/src/views/FeedView.vue`

- [ ] **Step 1: API client**

```typescript
addFeedSub: (body: { mid: string; sync_now?: boolean }) =>
  api<FeedSub>(`/api/v1/feed/subscriptions`, { method: 'POST', body: JSON.stringify(body) }),
removeFeedSub: (id: string) =>
  api<{ ok: boolean }>(`/api/v1/feed/subscriptions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
```

`FeedSub` 类型加 `sync_error?: string | null`。

- [ ] **Step 2: UI**

左侧：`<input v-model="newMid">` + 「添加」+ checkbox「并同步」；每行「删」`confirm` 后 remove。

更新 hint：可添加 mid / 删除。

- [ ] **Step 3: `npm run build`**

- [ ] **Step 4: Commit（仅用户要求时）**

---

### Task 3: 文档

- gap：可添加/删除 UP；建议下一刀关键词搜索 / Docker  
- smoke：Feed mid 添加、删除、可选同步  
- 相关测再跑 + build 可选  

---

## Spec coverage

| Spec | Task |
|------|------|
| profile + add/delete API | 1 |
| Feed UI | 2 |
| gap/smoke | 3 |
| 搜索 | 非目标 |

## Placeholder scan

`config_json` 默认与桌面一致即可（`{}` 或 `{"dynamics":true}`——若 sync 读 config.dynamics，查 ops 是否依赖；当前 sync 不读 config，用 `{}`）。
