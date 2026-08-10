# B 站信息流 Web 同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** zak2 自实现 B 站动态同步，Ops 可跑 `sync_bilibili_feed`，写入共用 `feed_items`。

**Architecture:** 精简移植 Cookie+WBI 客户端（用 **httpx**，不 import vnpy）；`ops_sync_bilibili_feed` 遍历启用订阅并按 `external_id` 去重插入；进 RUNNABLE + 默认定时。

**Tech Stack:** httpx、SQLAlchemy、APScheduler defaults、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-bilibili-feed-sync-design.md`

## Global Constraints

- 只改 zak2；不改 zak；**禁止** `import vnpy_*`
- 不新增 UP；不做通知；不做 feed_cursor 表
- Commit 仅用户明确要求时（默认跳过）
- 不打真 B 站（测全 mock）

**Clarifications:**

- HTTP 客户端用项目已有 `httpx`（勿新增 `requests` 依赖）
- 中国时区窗口：用 `ZoneInfo("Asia/Shanghai")`（或 `datetime`+固定偏移）判断 08≤hour<20
- 参考桌面逻辑可 **阅读** `zak/.../integrations/bilibili/*`，但代码须重写进 zak2

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/integrations/bilibili/__init__.py` | 包 |
| `backend/app/integrations/bilibili/client.py` | Cookie + WBI + get_json |
| `backend/app/integrations/bilibili/dynamics.py` | list_recent_dynamics |
| `backend/app/integrations/bilibili/normalize.py` | raw → draft dataclass |
| `backend/app/services/ops_sync_bilibili_feed.py` | sync job |
| `backend/tests/test_bilibili_normalize.py` | normalize 单测 |
| `backend/tests/test_ops_sync_bilibili_feed.py` | sync 单测 |
| `backend/app/core/settings.py` | `bilibili_cookies` |
| `backend/app/services/ops_catalog.py` / `ops_runners.py` / `scheduler_defaults.py` | 接线 |
| `frontend/src/views/FeedView.vue` / `OpsView.vue` | 文案 |
| `.env.example` / docs | 文档 |

---

### Task 1: bilibili 集成层（client / dynamics / normalize）

**Files:**
- Create: `backend/app/integrations/bilibili/{__init__,client,dynamics,normalize}.py`
- Create: `backend/tests/test_bilibili_normalize.py`

**Interfaces:**
```python
@dataclass
class FeedItemDraft:
    external_id: str
    item_type: str
    title: str
    summary: str
    url: str
    author_name: str
    published_at: str  # ISO
    payload: dict

class BilibiliApiError(Exception): ...
class BilibiliClient:
    def __init__(self, *, cookies: str = "", transport=None): ...
    @property
    def cookies_configured(self) -> bool: ...
    def get_json(self, path: str, *, params: dict | None = None, signed: bool = True) -> dict: ...

def list_recent_dynamics(client, mid: str, *, count: int = 10) -> list[dict]: ...
def normalize_dynamic(raw: dict, *, author_name: str) -> FeedItemDraft | None: ...
```

WBI：移植 mixin table + nav 取 key + md5 签名（对照桌面 `client.py`，改用 httpx）。

- [ ] **Step 1: 写 normalize 失败测**

```python
# backend/tests/test_bilibili_normalize.py
from app.integrations.bilibili.normalize import normalize_dynamic

def test_normalize_video_archive() -> None:
    raw = {
        "id_str": "123",
        "type": "DYNAMIC_TYPE_AV",
        "modules": {
            "module_author": {"pub_ts": 1700000000},
            "module_dynamic": {
                "major": {
                    "archive": {
                        "bvid": "BV1xx",
                        "title": "标题",
                        "desc": "简介",
                        "cover": "http://c",
                    }
                }
            },
        },
    }
    d = normalize_dynamic(raw, author_name="UP")
    assert d is not None
    assert d.external_id == "123"
    assert d.item_type == "video"
    assert d.title == "标题"
    assert "BV1xx" in d.url
    assert d.author_name == "UP"


def test_normalize_missing_id_returns_none() -> None:
    assert normalize_dynamic({"modules": {}}, author_name="x") is None
```

- [ ] **Step 2: 跑测确认失败** → 实现 normalize（精简移植桌面；可省略部分 edge，保留 archive / opus / 纯文案）

- [ ] **Step 3: 实现 client + dynamics**（可无单测打真网；可选 mock httpx 测 `cookies_configured`）

```python
# cookies_configured
assert BilibiliClient(cookies="").cookies_configured is False
assert BilibiliClient(cookies="SESSDATA=x").cookies_configured is True
```

`list_recent_dynamics`：`GET /x/polymer/web-dynamic/v1/feed/space`，params `host_mid` + features（同桌面常量）。

- [ ] **Step 4: 跑测**

```bash
cd backend && python -m pytest tests/test_bilibili_normalize.py -v
```

- [ ] **Step 5: Commit（仅用户要求时）**

---

### Task 2: `ops_sync_bilibili_feed` job

**Files:**
- Create: `backend/app/services/ops_sync_bilibili_feed.py`
- Create: `backend/tests/test_ops_sync_bilibili_feed.py`
- Modify: `backend/app/core/settings.py`（`bilibili_cookies: str = ""`）

**Interfaces:**
```python
JOB_ID = "sync_bilibili_feed"
FEED_RECENT_LIMIT = 10
SUBSCRIPTION_SLEEP_SEC = 0.01  # 测可 monkeypatch；生产 2.0~3.0

def in_sync_window(now=None) -> bool:  # Asia/Shanghai 8 <= hour < 20

def sync_bilibili_feed(db: Session, *, force: bool = False) -> dict:
    # returns {success, skipped?, message, new_items, errors?}
```

**算法：**
1. `force=False` 且非窗口 → skipped  
2. cookies = `get_settings().bilibili_cookies`；空 → skipped  
3. 查启用 `bilibili_up` 订阅；空 → skipped  
4. 每订阅：`list_recent_dynamics` → normalize → 若已存在 `(subscription_id, external_id)` skip；否则 INSERT  
5. 异常记入 errors；最后 `save_job_run_meta`  
6. `success=False` 仅当全部失败且有硬错误；部分成功仍 `success=True` 并带 errors（与桌面 JobResult 精神接近：有错误时 success=False 若全部失败——实现选：**有任意 API 错误则 success=False 但仍写入已成功的 items**；无 Cookie skip 为 success=True）

查重：
```python
select(FeedItem.id).where(FeedItem.subscription_id==..., FeedItem.external_id==...)
```

INSERT 字段对齐 `FeedItem` model。

- [ ] **Step 1: 写失败单测**

```python
def test_skip_no_cookies(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ops_sync_bilibili_feed.get_settings", lambda: SimpleNamespace(bilibili_cookies=""))
    out = sync_bilibili_feed(MagicMock(), force=True)
    assert out.get("skipped") is True

def test_insert_new_item(monkeypatch) -> None:
    # mock list enabled subs; mock dynamics; mock normalize; db.execute/scalars
    ...
```

- [ ] **Step 2–4: 实现 + 绿测**

```bash
cd backend && python -m pytest tests/test_ops_sync_bilibili_feed.py tests/test_bilibili_normalize.py -v
```

- [ ] **Step 5: Commit（仅用户要求时）**

---

### Task 3: RUNNABLE / cron / UI / 文档

**Files:**
- Modify: `ops_catalog.py` — `RUNNABLE` 加 id；更新 JobSpec 描述为 Web 可跑  
- Modify: `ops_runners.py` — 注册  
- Modify: `scheduler_defaults.py` — e.g. `"sync_bilibili_feed": {"hours": list(range(8, 20)), "minute": 15, "day_of_week": "mon-fri"}`（需确认 `build_cron` 支持 hours 列表，已有 `screen_intraday` 先例）  
- Modify: `test_ops_catalog.py` / `test_scheduler_defaults.py`  
- Modify: `FeedView.vue` / `OpsView.vue` 文案；Ops 快捷跑若需列入可跑 job  
- Modify: `.env.example`、`docs/gap-vs-desktop.md`、`docs/smoke-checklist.md`、README（若有）

Ops 手动跑：确认 `force` 参数路径——若现有 `POST .../run` 无 force，则定时受窗口限制，手动 run 时 **默认 force=True**（在 runner 包装里对 bilibili 传 force=True），避免 Ops 点了却被窗口 skip。

```python
# ops_runners 或 sync 入口
def _run_sync_bilibili_feed(db, **kwargs):
    return ops_sync_bilibili_feed.sync_bilibili_feed(db, force=True)
# embedded scheduler 调用时 force=False
```

若 scheduler 与手动共用同一 runner，则在 `ops.py` run 与 `_run_job` 分别传 force——查现有 `ops_runners` / `embedded_scheduler` 调用约定后二选一：
- **推荐**：`sync_bilibili_feed(db, *, force: bool = False)`；`RUNNERS` 存 lambda db: sync(..., force=True)；scheduler 直接 import 并 `force=False`。

- [ ] **Step 1: catalog/runner/cron + 测**

- [ ] **Step 2: UI + env + docs**

- [ ] **Step 3: 全相关测**

```bash
cd backend && python -m pytest tests/test_bilibili_normalize.py tests/test_ops_sync_bilibili_feed.py tests/test_ops_catalog.py tests/test_scheduler_defaults.py -q
cd ../frontend && npm run build
```

- [ ] **Step 4: Commit（仅用户要求时）**

---

## Spec coverage

| Spec | Task |
|------|------|
| client/dynamics/normalize | 1 |
| sync job + settings cookies | 2 |
| RUNNABLE/cron/UI/docs | 3 |
| 加 UP / vnpy import / 真网 | 非目标 |

## Placeholder scan

force 与 scheduler 接线以实现时代码为准（Step 写清推荐）；WBI 表从桌面复制常量。
