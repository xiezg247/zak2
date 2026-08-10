# 通知历史（自选只读）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 自选页可折叠只读通知投递历史（共用 `app.notify_delivery_log`）。

**Architecture:** `notify_log` 服务读 PG → `GET /watchlist/notify-log` → Watchlist 风控卡片下方懒加载折叠区。

**Tech Stack:** FastAPI、SQLAlchemy text、Vue WatchlistView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-07-notify-history-design.md`

## Global Constraints

- 只改 zak2；共用 PG，不改 zak 代码
- 只读；无发送/删日志/改订阅
- Commit 仅用户明确要求时（默认跳过）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/notify_log.py` | limit 夹逼、payload 解析、list_recent |
| `backend/app/schemas/watchlist.py` | NotifyLogItem / NotifyLogOut |
| `backend/app/api/v1/watchlist.py` | GET notify-log |
| `backend/tests/test_notify_log.py` | 服务 + API 单测 |
| `frontend/src/api/watchlist.ts` | 类型 + notifyLog() |
| `frontend/src/views/WatchlistView.vue` | 可折叠区 UI |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: notify_log 服务 + 单测

**Files:**
- Create: `backend/app/services/notify_log.py`
- Create: `backend/tests/test_notify_log.py`

**Interfaces:**
- `DEFAULT_LIMIT = 50`, `MAX_LIMIT = 100`
- `clamp_limit(raw: int | None) -> int` — None→50；≤0→1；>100→100
- `parse_payload(payload_json: str) -> dict` — loads；失败 `{ "_raw": 原文 }`
- `list_notify_log(db, user_id: str, *, limit: int | None = None) -> dict`  
  → `{ "items": [...], "limit": int, "count": int }`  
  每项：`id, event_type, channel, status, error, created_at, payload`

SQL（与桌面同表）：

```sql
SELECT id, event_type, channel, payload_json, status, error, created_at
FROM app.notify_delivery_log
WHERE user_id = CAST(:uid AS uuid)
ORDER BY created_at DESC
LIMIT :lim
```

- [ ] **Step 1: 写失败单测**

```python
from app.services.notify_log import clamp_limit, parse_payload

def test_clamp_limit() -> None:
    assert clamp_limit(None) == 50
    assert clamp_limit(0) == 1
    assert clamp_limit(200) == 100
    assert clamp_limit(50) == 50

def test_parse_payload_ok() -> None:
    assert parse_payload('{"a": 1}') == {"a": 1}

def test_parse_payload_raw() -> None:
    assert parse_payload("not-json") == {"_raw": "not-json"}
```

```python
# list_notify_log with MagicMock db
def test_list_empty() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []
    out = list_notify_log(db, "u1", limit=50)
    assert out["items"] == []
    assert out["count"] == 0
    assert out["limit"] == 50

def test_list_maps_payload() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {
            "id": "1",
            "event_type": "test",
            "channel": "feishu",
            "payload_json": '{"x": 1}',
            "status": "ok",
            "error": "",
            "created_at": "2026-08-07 10:00:00",
        }
    ]
    out = list_notify_log(db, "u1", limit=10)
    assert out["items"][0]["payload"] == {"x": 1}
    assert out["items"][0]["event_type"] == "test"
```

- [ ] **Step 2: RED** — `cd backend && python -m pytest tests/test_notify_log.py -v`（模块不存在）

- [ ] **Step 3: 实现 `notify_log.py`**

- [ ] **Step 4: GREEN** — 同上 pytest PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 2: Schema + API

**Files:**
- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/app/api/v1/watchlist.py`
- Modify: `backend/tests/test_notify_log.py`（追加 API 测）

**Schemas:**

```python
class NotifyLogItem(BaseModel):
    id: str
    event_type: str
    channel: str
    status: str
    error: str = ""
    created_at: str
    payload: dict[str, Any] = Field(default_factory=dict)

class NotifyLogOut(BaseModel):
    items: list[NotifyLogItem] = Field(default_factory=list)
    limit: int = 50
    count: int = 0
```

**Route:**

```python
@router.get("/watchlist/notify-log", response_model=NotifyLogOut)
def get_notify_log(
    limit: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotifyLogOut:
    return NotifyLogOut(**notify_log.list_notify_log(db, str(user.id), limit=limit))
```

- [ ] **Step 1: API 单测**（参照 `test_trading_risk.py` / `test_limit_list_api.py`：override `get_current_user` + `get_db`，patch `list_notify_log`）

```python
def test_api_notify_log_ok(client, ...) -> None:
    with patch("app.api.v1.watchlist.notify_log.list_notify_log", return_value={...}):
        resp = client.get("/api/v1/watchlist/notify-log?limit=10")
    assert resp.status_code == 200
    assert resp.json()["count"] == ...
```

- [ ] **Step 2–3: 实现 schema/route；pytest PASS**

- [ ] **Step 4: Commit** — 跳过

---

### Task 3: 前端 + 文档 + 全量

**Files:**
- Modify: `frontend/src/api/watchlist.ts`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

**API client:**

```ts
export type NotifyLogItem = {
  id: string
  event_type: string
  channel: string
  status: string
  error: string
  created_at: string
  payload: Record<string, unknown>
}
export type NotifyLogOut = { items: NotifyLogItem[]; limit: number; count: number }

// watchlistApi.notifyLog: (limit?: number) => api<NotifyLogOut>(`/api/v1/watchlist/notify-log?...`)
```

**UI（WatchlistView）：**
- 风控卡片下方可折叠「通知历史」；默认折叠
- 首次展开 / 点刷新 → `notifyLog()`
- 表：时间·事件·渠道·状态·错误；点击行展开 `<pre>{{ pretty(payload) }}</pre>`
- 失败态 `warn`/`err`；空态文案；加载中文提示
- 匹配现有 CSS，不进导航

**Docs：**
- gap：风控通知行注明「通知历史只读」；下一刀另定（去掉「下一刀=通知历史」）
- smoke：自选可展开通知历史

- [ ] **Step 1: 实现前端**
- [ ] **Step 2: `cd frontend && npm run build`**
- [ ] **Step 3: `cd backend && python -m pytest`**
- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage

| Spec | Task |
|------|------|
| clamp / parse / list | 1 |
| GET API + schemas | 2 |
| 自选 UI + docs + 验收 | 3 |

无 TBD。
