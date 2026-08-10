# 信息流关键词搜索 UP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** Feed 可按关键词搜索 B 站 UP，点选后走现有 `POST /feed/subscriptions` 添加；保留 mid 直填。

**Architecture:** 移植桌面 `search_users`（WBI `search/type`）到 `integrations/bilibili/user.py`；`feed.search_bilibili_ups` 校验 Cookie 并夹 limit；`GET /feed/bilibili/search` 返回候选；FeedView 独立关键词区 + 结果行「添加」。

**Tech Stack:** FastAPI、已有 `BilibiliClient.get_json`、Vue FeedView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-feed-search-up-design.md`

## Global Constraints

- 只改 zak2；不改 zak；不 import vnpy_*
- 不改 `add_bilibili_up` / 删除 / 同步 job 语义；不盲加搜索第一条
- Commit 仅用户明确要求时（默认跳过 Step Commit）
- 不打真 B 站（全部 mock）

**Clarifications:**

- 搜索路径：`/x/web-interface/wbi/search/type`，`search_type=bili_user`，`signed=True`
- 客户端用 `client.get_json`（勿用桌面 `_get_json`）
- `limit` 默认 8，夹在 1–20（服务层 `max(1, min(20, limit))`；Query 亦 `ge=1, le=20`）
- 无 Cookie → 400「未配置 BILIBILI_COOKIES」（与 add 一致；先于空 q）
- `q` strip 后空 → `{results: []}`（有 Cookie 时）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/integrations/bilibili/user.py` | 增 `search_users` / `_iter_search_user_items` / `_normalize_search_user` |
| `backend/app/services/feed.py` | 增 `search_bilibili_ups` |
| `backend/app/schemas/content.py` | `BilibiliUserHit` / `BilibiliSearchOut` |
| `backend/app/api/v1/content.py` | `GET /feed/bilibili/search` |
| `backend/tests/test_bilibili_user_search.py` | **新建** normalize / iter / search_users mock |
| `backend/tests/test_feed_search.py` | **新建** Cookie / 空 q / 成功路径 |
| `frontend/src/api/content.ts` | `searchBilibiliUps` + 类型 |
| `frontend/src/views/FeedView.vue` | 关键词搜索 UI + 点选添加 |
| `docs/gap-vs-desktop.md` / `docs/smoke-checklist.md` | 缺口与 smoke |

---

### Task 1: `search_users` + 单测

**Files:**
- Modify: `backend/app/integrations/bilibili/user.py`
- Create: `backend/tests/test_bilibili_user_search.py`

**Interfaces:**
```python
# user.py（与 get_user_profile 同文件）
_SEARCH_USER_PATH = "/x/web-interface/wbi/search/type"

def search_users(client: BilibiliClient, keyword: str, *, limit: int = 8) -> list[dict[str, str]]:
    ...

def _iter_search_user_items(result: Any): ...
def _normalize_search_user(item: dict[str, Any]) -> dict[str, str] | None:
    # → {mid, name, avatar, sign} 或 None
```

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_bilibili_user_search.py
"""B 站用户搜索单测（mock，不打真站）。"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.integrations.bilibili.user import (
    _iter_search_user_items,
    _normalize_search_user,
    search_users,
)


def test_iter_search_user_items_flat_wbi_result() -> None:
    rows = list(
        _iter_search_user_items(
            [
                {"type": "bili_user", "mid": 1, "uname": "A"},
                {"type": "video", "bvid": "BV1"},
            ]
        )
    )
    assert len(rows) == 1
    assert rows[0]["mid"] == 1


def test_iter_search_user_items_legacy_grouped_result() -> None:
    rows = list(
        _iter_search_user_items(
            [
                {
                    "result_type": "bili_user",
                    "data": [{"mid": 2, "uname": "B"}],
                }
            ]
        )
    )
    assert len(rows) == 1
    assert rows[0]["uname"] == "B"


def test_normalize_search_user_prefixes_avatar() -> None:
    user = _normalize_search_user({"mid": 3, "uname": "C", "upic": "//example.com/a.jpg"})
    assert user is not None
    assert user["avatar"] == "https://example.com/a.jpg"
    assert user["name"] == "C"
    assert user["mid"] == "3"


def test_normalize_search_user_skips_empty_mid() -> None:
    assert _normalize_search_user({"uname": "X"}) is None


def test_search_users_empty_keyword() -> None:
    client = MagicMock()
    assert search_users(client, "  ") == []
    client.get_json.assert_not_called()


def test_search_users_calls_signed_path_and_limits() -> None:
    client = MagicMock()
    client.get_json.return_value = {
        "result": [
            {"type": "bili_user", "mid": i, "uname": f"U{i}", "upic": ""}
            for i in range(1, 12)
        ]
    }
    out = search_users(client, "量化", limit=3)
    assert len(out) == 3
    assert out[0]["mid"] == "1"
    client.get_json.assert_called_once_with(
        "/x/web-interface/wbi/search/type",
        params={"search_type": "bili_user", "keyword": "量化", "page": 1},
        signed=True,
    )
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_bilibili_user_search.py -v
```

Expected: FAIL（`search_users` / helpers 未定义或 ImportError）

- [ ] **Step 3: 实现 `user.py` 增量**

在 `get_user_profile` **之上或之下**追加（保留现有 `get_user_profile` 不变）：

```python
from typing import Any

_SEARCH_USER_PATH = "/x/web-interface/wbi/search/type"


def search_users(client: BilibiliClient, keyword: str, *, limit: int = 8) -> list[dict[str, str]]:
    keyword = keyword.strip()
    if not keyword:
        return []
    data = client.get_json(
        _SEARCH_USER_PATH,
        params={
            "search_type": "bili_user",
            "keyword": keyword,
            "page": 1,
        },
        signed=True,
    )
    users: list[dict[str, str]] = []
    for item in _iter_search_user_items(data.get("result")):
        user = _normalize_search_user(item)
        if user is None:
            continue
        users.append(user)
        if len(users) >= limit:
            break
    return users


def _iter_search_user_items(result: Any):
    if not isinstance(result, list):
        return
    for item in result:
        if not isinstance(item, dict):
            continue
        if str(item.get("result_type") or "") == "bili_user":
            for row in item.get("data") or []:
                if isinstance(row, dict):
                    yield row
            continue
        if str(item.get("type") or "") == "bili_user":
            yield item


def _normalize_search_user(item: dict[str, Any]) -> dict[str, str] | None:
    mid = str(item.get("mid") or "")
    if not mid:
        return None
    avatar = str(item.get("upic") or item.get("face") or "")
    if avatar.startswith("//"):
        avatar = f"https:{avatar}"
    return {
        "mid": mid,
        "name": str(item.get("uname") or item.get("title") or ""),
        "avatar": avatar,
        "sign": str(item.get("usign") or item.get("sign") or ""),
    }
```

参考（只读，禁止 import）：`zak/packages/vnpy-ashare/vnpy_ashare/integrations/bilibili/user.py`

- [ ] **Step 4: 跑测绿**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_bilibili_user_search.py -v
```

Expected: PASS

- [ ] **Step 5: Commit（仅用户要求时）**

```bash
git add backend/app/integrations/bilibili/user.py backend/tests/test_bilibili_user_search.py
git commit -m "$(cat <<'EOF'
feat(feed): 移植 B 站 UP 关键词搜索到 integrations

EOF
)"
```

---

### Task 2: `search_bilibili_ups` + schema + API

**Files:**
- Modify: `backend/app/services/feed.py`
- Modify: `backend/app/schemas/content.py`
- Modify: `backend/app/api/v1/content.py`
- Create: `backend/tests/test_feed_search.py`

**Interfaces:**
```python
# feed.py
def search_bilibili_ups(q: str, *, limit: int = 8) -> list[dict[str, str]]:
    # cookies 空 → HTTPException 400「未配置 BILIBILI_COOKIES」
    # limit = max(1, min(20, int(limit)))
    # q strip 空 → []
    # BilibiliClient + search_users → list[{mid,name,avatar,sign}]

# schemas
class BilibiliUserHit(BaseModel):
    mid: str
    name: str
    avatar: str = ""
    sign: str = ""

class BilibiliSearchOut(BaseModel):
    results: list[BilibiliUserHit]

# API
# GET /feed/bilibili/search?q=&limit=8  → BilibiliSearchOut
```

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_feed_search.py
"""feed 关键词搜索 UP（mock）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services import feed as feed_svc


def _settings(cookies: str = "SESSDATA=x") -> SimpleNamespace:
    return SimpleNamespace(bilibili_cookies=cookies)


def test_search_requires_cookies(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings(""))
    with pytest.raises(HTTPException) as ei:
        feed_svc.search_bilibili_ups("量化")
    assert ei.value.status_code == 400
    assert "BILIBILI" in ei.value.detail or "COOKIE" in ei.value.detail.upper()


def test_search_empty_q_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    with patch.object(feed_svc, "search_users") as su:
        assert feed_svc.search_bilibili_ups("  ") == []
        su.assert_not_called()


def test_search_success_clamps_limit(monkeypatch) -> None:
    monkeypatch.setattr(feed_svc, "get_settings", lambda: _settings())
    hits = [{"mid": "1", "name": "A", "avatar": "", "sign": ""}]
    with (
        patch.object(feed_svc, "BilibiliClient") as client_cls,
        patch.object(feed_svc, "search_users", return_value=hits) as su,
    ):
        client_cls.return_value = MagicMock()
        out = feed_svc.search_bilibili_ups("量化", limit=99)
    assert out == hits
    su.assert_called_once()
    assert su.call_args.kwargs.get("limit") == 20 or su.call_args[1].get("limit") == 20
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_feed_search.py -v
```

Expected: FAIL（`search_bilibili_ups` 不存在）

- [ ] **Step 3: 实现 service + schema + API**

`schemas/content.py` 在 `FeedSubCreate` 附近追加：

```python
class BilibiliUserHit(BaseModel):
    mid: str
    name: str
    avatar: str = ""
    sign: str = ""


class BilibiliSearchOut(BaseModel):
    results: list[BilibiliUserHit]
```

`feed.py`：

```python
from app.integrations.bilibili.user import get_user_profile, search_users

def search_bilibili_ups(q: str, *, limit: int = 8) -> list[dict[str, str]]:
    cookies = (get_settings().bilibili_cookies or "").strip()
    if not cookies:
        raise HTTPException(status_code=400, detail="未配置 BILIBILI_COOKIES")
    limit = max(1, min(20, int(limit)))
    q = str(q or "").strip()
    if not q:
        return []
    client = BilibiliClient(cookies=cookies)
    try:
        return search_users(client, q, limit=limit)
    finally:
        client.close()
```

`content.py` API（订阅路由附近，import `BilibiliSearchOut`）：

```python
@router.get("/feed/bilibili/search", response_model=BilibiliSearchOut)
def get_bilibili_search(
    q: str = Query(""),
    limit: int = Query(default=8, ge=1, le=20),
    user: User = Depends(get_current_user),
) -> BilibiliSearchOut:
    rows = feed_svc.search_bilibili_ups(q, limit=limit)
    return BilibiliSearchOut(results=rows)
```

- [ ] **Step 4: 跑测绿**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_bilibili_user_search.py tests/test_feed_search.py tests/test_feed_subscriptions.py -v
```

Expected: PASS

- [ ] **Step 5: Commit（仅用户要求时）**

```bash
git add backend/app/services/feed.py backend/app/schemas/content.py backend/app/api/v1/content.py backend/tests/test_feed_search.py
git commit -m "$(cat <<'EOF'
feat(feed): 增加关键词搜索 UP API

EOF
)"
```

---

### Task 3: Feed UI

**Files:**
- Modify: `frontend/src/api/content.ts`
- Modify: `frontend/src/views/FeedView.vue`

**Interfaces:**
```typescript
export type BilibiliUserHit = { mid: string; name: string; avatar: string; sign: string }

searchBilibiliUps: (q: string, limit?: number) =>
  api<{ results: BilibiliUserHit[] }>(
    `/api/v1/feed/bilibili/search?q=${encodeURIComponent(q)}&limit=${limit ?? 8}`,
  )
```

- [ ] **Step 1: API client**

在 `content.ts` 增加类型与方法：

```typescript
export type BilibiliUserHit = {
  mid: string
  name: string
  avatar: string
  sign: string
}

// contentApi 内：
searchBilibiliUps: (q: string, limit = 8) =>
  api<{ results: BilibiliUserHit[] }>(
    `/api/v1/feed/bilibili/search?q=${encodeURIComponent(q)}&limit=${limit}`,
  ),
```

- [ ] **Step 2: FeedView 搜索区**

保留现有 mid 行与「并同步」。在 mid 行**下方**增加：

状态：

```typescript
const searchQ = ref('')
const searchHits = ref<BilibiliUserHit[]>([])
const searching = ref(false)
const searchTried = ref(false)
```

逻辑：

```typescript
async function runSearch() {
  const q = searchQ.value.trim()
  searching.value = true
  error.value = ''
  searchTried.value = true
  try {
    const res = await contentApi.searchBilibiliUps(q)
    searchHits.value = res.results
  } catch (e) {
    searchHits.value = []
    error.value = e instanceof Error ? e.message : '搜索失败'
  } finally {
    searching.value = false
  }
}

async function addFromHit(hit: BilibiliUserHit) {
  adding.value = true
  error.value = ''
  try {
    const sub = await contentApi.addFeedSub({ mid: hit.mid, sync_now: syncOnAdd.value })
    const syncErr = sub.sync_error
    await load()
    if (syncErr) {
      error.value = `已添加，但同步失败：${syncErr}`
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '添加失败'
  } finally {
    adding.value = false
  }
}
```

模板（左侧 mid 区后）：

```html
<div class="row">
  <input v-model="searchQ" placeholder="关键词搜 UP" @keyup.enter="runSearch" />
  <button type="button" class="ghost" :disabled="searching" @click="runSearch">搜索</button>
</div>
<div v-if="searchHits.length" class="hits">
  <div v-for="h in searchHits" :key="h.mid" class="hit-row">
    <img v-if="h.avatar" class="avatar" :src="h.avatar" alt="" />
    <div class="hit-meta">
      <div class="hit-name">{{ h.name || h.mid }}</div>
      <div class="muted tiny-text">mid {{ h.mid }}</div>
    </div>
    <button type="button" class="tiny" :disabled="adding" @click="addFromHit(h)">添加</button>
  </div>
</div>
<p v-else-if="searchTried && !searching" class="muted tiny-text">无搜索结果</p>
```

样式补充（scoped，贴合现有）：

```css
.hits {
  display: grid;
  gap: 6px;
}
.hit-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: center;
}
.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
}
.hit-name {
  font-size: 0.9rem;
}
.tiny-text {
  font-size: 0.75rem;
}
```

更新 hint：可 mid 直填，或关键词搜索后点选添加。

- [ ] **Step 3: `npm run build`**

```bash
cd /Users/xiezhigang/Projects/me/zak2/frontend && npm run build
```

Expected: 成功退出 0

- [ ] **Step 4: Commit（仅用户要求时）**

```bash
git add frontend/src/api/content.ts frontend/src/views/FeedView.vue
git commit -m "$(cat <<'EOF'
feat(feed): Feed 页支持关键词搜索并点选添加 UP

EOF
)"
```

---

### Task 4: 文档 + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap**

「守则 / 笔记 / 信息流」行：注明可关键词搜索 UP 后点选添加。

「建议下一刀」：去掉「关键词搜索 UP」；保留 Docker 全家桶等。

- [ ] **Step 2: smoke**

`/feed` 条目追加：关键词搜索 → 结果点「添加」走现有添加路径（可勾选并同步）；亦可 `pytest tests/test_bilibili_user_search.py tests/test_feed_search.py`。

- [ ] **Step 3: 相关测 + build**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_bilibili_user_search.py tests/test_feed_search.py tests/test_feed_subscriptions.py -v
cd /Users/xiezhigang/Projects/me/zak2/frontend && npm run build
```

可选全量：`python -m pytest -q`

- [ ] **Step 4: Commit（仅用户要求时）**

```bash
git add docs/gap-vs-desktop.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 记录 Feed 关键词搜索 UP 与 smoke 项

EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| `search_users` WBI + normalize | 1 |
| `search_bilibili_ups` + Cookie/空 q/limit | 2 |
| `GET /feed/bilibili/search` + schemas | 2 |
| Feed 独立关键词 + 点选 `POST subscriptions` | 3 |
| 保留 mid 直填 | 3（不删现有 UI） |
| gap / smoke | 4 |
| 盲加第一条 / 改 add 语义 / 改 zak | 非目标 |

## Placeholder scan

无 TBD；`client.get_json` 与桌面 `_get_json` 差异已写明；limit 夹紧在 service + Query 双层。
