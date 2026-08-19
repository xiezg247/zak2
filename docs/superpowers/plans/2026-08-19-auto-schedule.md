# 自动任务（用户自定义选股定时）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增「自动任务」模块，用户创建自己的选股任务（配方 + 星期几 + 一天多时刻），到点自动跑配方选股并推送到已配渠道。

**Architecture:** 分钟级守护轮询 + ARQ。内嵌 APScheduler 新增每分钟守护 job `auto_schedule_poll`，扫描 `app.auto_schedule` 表中命中当前「星期几 + HH:MM」的启用任务，以稳定 job id `auto:{task_id}` 入队 ARQ；worker 侧 `run_auto_schedule_task` 复用 `run_recipe_screen` 执行选股、写历史、更新任务 meta、推送渠道。API 提供按用户隔离的 CRUD + 启停。

**Tech Stack:** FastAPI / SQLAlchemy / Alembic / ARQ / APScheduler / Vue 3 + TypeScript

## Global Constraints

- Python 类型标注必须完整（mypy `disallow_untyped_defs = true`），行宽 ≤ 120
- commit message 用简体中文，格式 `<type>(<scope>): <简述>`
- 配方校验复用 `app.services.screener.presets.get_builtin_recipe`
- 时间戳字符串统一 `datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")`；调度匹配用北京时间（`app.core.time.china_now`）
- 前端 TypeScript 必须通过 `vue-tsc` 与 `eslint`（`npm run build` 通过）
- 所有路由走 `get_current_user`，只操作当前用户自己的任务

---

### Task 1: 数据模型与 Alembic 迁移

**Files:**
- Create: `backend/app/models/auto_schedule.py`
- Create: `backend/alembic/versions/013_auto_schedule.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_auto_schedule_model.py`

**Interfaces:**
- Produces: `app.models.auto_schedule.AutoSchedule`（字段：id/user_id/name/recipe_id/days_of_week/times/enabled/last_run_at/last_message/last_success/created_at/updated_at）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_auto_schedule_model.py
from __future__ import annotations

from app.models.auto_schedule import AutoSchedule


def test_model_columns() -> None:
    cols = AutoSchedule.__table__.columns
    assert "id" in cols
    assert "user_id" in cols
    assert "name" in cols
    assert "recipe_id" in cols
    assert "days_of_week" in cols
    assert "times" in cols
    assert "enabled" in cols
    assert "last_run_at" in cols
    assert "last_message" in cols
    assert "last_success" in cols
    assert "created_at" in cols
    assert "updated_at" in cols
    assert cols["id"].autoincrement is not False
```

Run: `cd backend && uv run pytest tests/test_auto_schedule_model.py -v`
Expected: FAIL（`AutoSchedule` 未定义）

- [ ] **Step 2: 创建模型**

```python
# backend/app/models/auto_schedule.py
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AutoSchedule(Base):
    """自动任务（app.auto_schedule）。"""

    __tablename__ = "auto_schedule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    recipe_id: Mapped[str] = mapped_column(String(64), nullable=False)
    days_of_week: Mapped[str] = mapped_column(Text, nullable=False)
    times: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && uv run pytest tests/test_auto_schedule_model.py -v`
Expected: PASS

- [ ] **Step 4: 写迁移**

参考 `012_notify_channel` 风格：

```python
# backend/alembic/versions/013_auto_schedule.py
"""app.auto_schedule 自动任务表。"""

from alembic import op

revision = "013_auto_schedule"
down_revision = "012_notify_channel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.auto_schedule (
          id bigserial PRIMARY KEY,
          user_id uuid NOT NULL,
          name varchar(64) NOT NULL,
          recipe_id varchar(64) NOT NULL,
          days_of_week text NOT NULL,
          times jsonb NOT NULL DEFAULT '[]',
          enabled boolean NOT NULL DEFAULT TRUE,
          last_run_at text,
          last_message text,
          last_success boolean,
          created_at text NOT NULL,
          updated_at text NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_auto_schedule_user ON app.auto_schedule (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.auto_schedule")
```

- [ ] **Step 5: 注册模型**

```python
# backend/app/models/__init__.py —— 在 import 区加一行
from app.models.auto_schedule import AutoSchedule
# __all__ 加入 "AutoSchedule"
```

- [ ] **Step 6: 迁移 dry-run 验证**

Run: `cd backend && uv run alembic upgrade head`
Expected: 无报错，`app.auto_schedule` 表已建

- [ ] **Step 7: 提交**

```bash
git add backend/alembic/versions/013_auto_schedule.py backend/app/models/auto_schedule.py backend/app/models/__init__.py backend/tests/test_auto_schedule_model.py
git commit -m "feat(model): 新增自动任务表 app.auto_schedule"
```

---

### Task 2: 时间匹配纯函数

**Files:**
- Create: `backend/app/services/ops/auto_schedule_time.py`
- Test: `backend/tests/test_auto_schedule_time.py`

**Interfaces:**
- Produces:
  - `WEEKDAY_NAMES: dict[str, int]`（mon=0 … sun=6）
  - `parse_days_of_week(raw: str) -> list[int]`（支持 `mon-fri` 范围与 `mon,wed,fri` 列表及混合，非法抛 `ValueError`）
  - `parse_times(times: list[str]) -> list[str]`（校验 `HH:MM`，返回排序去重列表，非法或为空抛 `ValueError`）
  - `matches_now(days: list[int], times: list[str], now: datetime) -> bool`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_auto_schedule_time.py
from __future__ import annotations

from datetime import datetime

import pytest

from app.core.time import CHINA_TZ
from app.services.ops.auto_schedule_time import (
    matches_now,
    parse_days_of_week,
    parse_times,
)

MON = datetime(2026, 8, 17, 9, 35, tzinfo=CHINA_TZ)  # 周一 09:35
SAT = datetime(2026, 8, 22, 9, 35, tzinfo=CHINA_TZ)  # 周六 09:35


def test_parse_days_range() -> None:
    assert parse_days_of_week("mon-fri") == [0, 1, 2, 3, 4]


def test_parse_days_list() -> None:
    assert parse_days_of_week("mon,wed,fri") == [0, 2, 4]


def test_parse_days_mixed() -> None:
    assert parse_days_of_week("mon,wed-fri") == [0, 2, 3, 4]


def test_parse_days_uppercase_ok() -> None:
    assert parse_days_of_week("Mon,Fri") == [0, 4]


def test_parse_days_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_days_of_week("monday")


def test_parse_days_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_days_of_week("")


def test_parse_times_normalizes() -> None:
    assert parse_times(["09:35", "14:00", "09:35"]) == ["09:35", "14:00"]


def test_parse_times_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_times(["9:35"])


def test_parse_times_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_times([])


def test_matches_day_and_time() -> None:
    assert matches_now([0, 1, 2, 3, 4], ["09:35", "14:00"], MON) is True


def test_matches_time_but_wrong_day() -> None:
    assert matches_now([0, 1, 2, 3, 4], ["09:35"], SAT) is False


def test_matches_day_but_wrong_time() -> None:
    assert matches_now([0, 1, 2, 3, 4], ["14:00"], MON) is False
```

Run: `cd backend && uv run pytest tests/test_auto_schedule_time.py -v`
Expected: FAIL（`auto_schedule_time` 模块不存在）

- [ ] **Step 2: 实现**

```python
# backend/app/services/ops/auto_schedule_time.py
"""自动任务调度匹配：星期与时刻的解析、匹配。"""

from __future__ import annotations

import re
from datetime import datetime

WEEKDAY_NAMES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_days_of_week(raw: str) -> list[int]:
    """解析 'mon-fri' / 'mon,wed,fri'（支持混合）→ 升序 weekday 索引列表（mon=0）。"""
    days: set[int] = set()
    for item in str(raw).strip().lower().split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            start_name, end_name = item.split("-", 1)
            if start_name not in WEEKDAY_NAMES or end_name not in WEEKDAY_NAMES:
                raise ValueError(f"非法星期：{item}")
            start, end = WEEKDAY_NAMES[start_name], WEEKDAY_NAMES[end_name]
            if start > end:
                raise ValueError(f"非法星期范围：{item}")
            days.update(range(start, end + 1))
        else:
            if item not in WEEKDAY_NAMES:
                raise ValueError(f"非法星期：{item}")
            days.add(WEEKDAY_NAMES[item])
    if not days:
        raise ValueError("至少需要一个执行星期")
    return sorted(days)


def parse_times(times: list[str]) -> list[str]:
    """校验 'HH:MM' 列表，返回排序去重结果；非法或为空抛 ValueError。"""
    out: set[str] = set()
    for raw in times:
        value = str(raw).strip()
        if not _TIME_RE.fullmatch(value):
            raise ValueError(f"非法时刻：{value}")
        out.add(value)
    if not out:
        raise ValueError("至少需要一个执行时刻")
    return sorted(out)


def matches_now(days: list[int], times: list[str], now: datetime) -> bool:
    """当前时刻是否命中星期列表与时刻列表。"""
    if now.weekday() not in days:
        return False
    hhmm = f"{now.hour:02d}:{now.minute:02d}"
    return hhmm in times
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && uv run pytest tests/test_auto_schedule_time.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/ops/auto_schedule_time.py backend/tests/test_auto_schedule_time.py
git commit -m "feat(ops): 新增自动任务时间匹配函数"
```

---

### Task 3: Schemas 与 Repository

**Files:**
- Create: `backend/app/schemas/auto_schedule.py`
- Create: `backend/app/repositories/auto_schedule.py`
- Test: `backend/tests/test_auto_schedule_repo.py`

**Interfaces:**
- Consumes: Task 1 `AutoSchedule` 模型
- Produces:
  - `AutoScheduleCreate`（name/recipe_id/days_of_week/times）
  - `AutoScheduleUpdate`（全部可选）
  - `AutoScheduleOut`（id:int + 全部字段 + last_* 可为空）
  - `AutoScheduleListOut`（items）
  - `AutoScheduleEnabledPatch`（enabled）
  - `AutoScheduleRepository`：`create_task(name, recipe_id, days_of_week, times, enabled=True)`、`update_task(key, values)`、`get_any(key)`（跨用户）、`to_out(task)`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_auto_schedule_repo.py
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.auto_schedule import AutoSchedule
from app.repositories.auto_schedule import AutoScheduleRepository


def _row() -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        user_id="u1",
        name="盘中自动",
        recipe_id="intraday_multi",
        days_of_week="mon-fri",
        times=["09:35", "14:00"],
        enabled=True,
        last_run_at=None,
        last_message=None,
        last_success=None,
        created_at="2026-08-19 10:00:00",
        updated_at="2026-08-19 10:00:00",
    )


def test_repo_create_task_generates_fields() -> None:
    db = MagicMock()
    repo = AutoScheduleRepository(db, "u1")
    repo.create_task(
        name="盘中自动",
        recipe_id="intraday_multi",
        days_of_week="mon-fri",
        times=["09:35", "14:00"],
    )
    added = db.add.call_args.args[0]
    assert isinstance(added, AutoSchedule)
    assert added.user_id == "u1"
    assert added.name == "盘中自动"
    assert added.recipe_id == "intraday_multi"
    assert added.days_of_week == "mon-fri"
    assert added.times == ["09:35", "14:00"]
    assert added.enabled is True
    assert added.last_success is None


def test_repo_get_any_cross_user() -> None:
    db = MagicMock()
    db.get.return_value = _row()
    repo = AutoScheduleRepository(db, "u-other")
    out = repo.get_any(7)
    assert out is not None
    assert out.id == 7
    assert db.get.call_args.args[0] is AutoSchedule
    assert db.get.call_args.args[1] == 7


def test_repo_to_out_maps() -> None:
    repo = AutoScheduleRepository(MagicMock(), "u1")
    out = repo.to_out(_row())
    assert out.id == 7
    assert out.name == "盘中自动"
    assert out.times == ["09:35", "14:00"]
    assert out.last_success is None


def test_repo_update_partial() -> None:
    db = MagicMock()
    row = _row()
    db.scalar.return_value = row
    db.refresh.side_effect = lambda _: None
    repo = AutoScheduleRepository(db, "u1")
    out = repo.update_task(7, {"times": ["09:35"]})
    assert out is row
    assert row.times == ["09:35"]
    db.commit.assert_called_once()
```

Run: `cd backend && uv run pytest tests/test_auto_schedule_repo.py -v`
Expected: FAIL

- [ ] **Step 2: 实现 Schemas**

```python
# backend/app/schemas/auto_schedule.py
from __future__ import annotations

from pydantic import BaseModel, Field


class AutoScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    recipe_id: str = Field(min_length=1)
    days_of_week: str = Field(min_length=1)
    times: list[str] = Field(min_length=1)


class AutoScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    recipe_id: str | None = None
    days_of_week: str | None = None
    times: list[str] | None = None


class AutoScheduleEnabledPatch(BaseModel):
    enabled: bool


class AutoScheduleOut(BaseModel):
    id: int
    name: str
    recipe_id: str
    days_of_week: str
    times: list[str]
    enabled: bool
    last_run_at: str | None = None
    last_message: str | None = None
    last_success: bool | None = None
    created_at: str
    updated_at: str


class AutoScheduleListOut(BaseModel):
    items: list[AutoScheduleOut]
```

- [ ] **Step 3: 实现 Repository**

```python
# backend/app/repositories/auto_schedule.py
"""自动任务仓库（app.auto_schedule）。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.auto_schedule import AutoSchedule
from app.repositories.base import BaseRepository
from app.schemas.auto_schedule import AutoScheduleOut


def _now_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class AutoScheduleRepository(BaseRepository[AutoSchedule]):
    model = AutoSchedule
    order_by = (AutoSchedule.created_at,)

    def get_any(self, key: int) -> AutoSchedule | None:
        """跨用户读取（供 worker 按任务 id 执行）。"""
        return self.db.get(AutoSchedule, key)

    def to_out(self, task: AutoSchedule) -> AutoScheduleOut:
        return AutoScheduleOut(
            id=task.id,
            name=task.name,
            recipe_id=task.recipe_id,
            days_of_week=task.days_of_week,
            times=list(task.times or []),
            enabled=task.enabled,
            last_run_at=task.last_run_at,
            last_message=task.last_message,
            last_success=task.last_success,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    def create_task(
        self,
        *,
        name: str,
        recipe_id: str,
        days_of_week: str,
        times: list[str],
        enabled: bool = True,
    ) -> AutoSchedule:
        now = _now_str()
        return self.create(
            name=name,
            recipe_id=recipe_id,
            days_of_week=days_of_week,
            times=times,
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )

    def update_task(self, key: int, values: dict[str, Any]) -> AutoSchedule | None:
        values = dict(values)
        if values:
            values["updated_at"] = _now_str()
        return self.update(key, **values)
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && uv run pytest tests/test_auto_schedule_repo.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/auto_schedule.py backend/app/repositories/auto_schedule.py backend/tests/test_auto_schedule_repo.py
git commit -m "feat(api): 新增自动任务 schema 与仓库"
```

---

### Task 4: ARQ 入队函数

**Files:**
- Modify: `backend/app/services/ops/arq_jobs.py`
- Test: `backend/tests/test_auto_schedule_enqueue.py`

**Interfaces:**
- Consumes: `_arq_pool` / `_clear_arq_job_keys` / `_IN_FLIGHT`（arq_jobs 内部既有）
- Produces:
  - `auto_arq_id(task_id: str) -> str`（`auto:{task_id}`）
  - `enqueue_auto_task(task_id: str) -> str`（async，稳定 job id 防重）
  - `enqueue_auto_task_sync(task_id: str) -> str`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_auto_schedule_enqueue.py
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from app.services.ops import arq_jobs


def test_auto_arq_id() -> None:
    assert arq_jobs.auto_arq_id("7") == "auto:7"


def test_enqueue_auto_task_uses_stable_id() -> None:
    pool = MagicMock()
    job = MagicMock()
    job.job_id = "auto:7"
    pool.enqueue_job.return_value = job

    async def _go() -> str:
        with (
            patch.object(arq_jobs, "_arq_pool", return_value=pool),
            patch("app.core.settings.get_settings") as gs,
        ):
            gs.return_value.arq_queue_name = "zak2:arq"
            probe = MagicMock()
            probe.status.return_value = "not_found"
            with patch("app.services.ops.arq_jobs.Job", return_value=probe):
                return await arq_jobs.enqueue_auto_task("7")

    arq_id = asyncio.run(_go())
    assert arq_id == "auto:7"
    assert pool.enqueue_job.call_args.args[0] == "run_auto_schedule_task"
    assert pool.enqueue_job.call_args.args[1] == "7"
    assert pool.enqueue_job.call_args.kwargs["_job_id"] == "auto:7"


def test_enqueue_auto_task_reuses_inflight() -> None:
    pool = MagicMock()

    async def _go() -> str:
        with (
            patch.object(arq_jobs, "_arq_pool", return_value=pool),
            patch("app.core.settings.get_settings") as gs,
        ):
            gs.return_value.arq_queue_name = "zak2:arq"
            probe = MagicMock()
            probe.status.return_value = "in_progress"
            with patch("app.services.ops.arq_jobs.Job", return_value=probe):
                return await arq_jobs.enqueue_auto_task("7")

    arq_id = asyncio.run(_go())
    assert arq_id == "auto:7"
    pool.enqueue_job.assert_not_called()
```

Run: `cd backend && uv run pytest tests/test_auto_schedule_enqueue.py -v`
Expected: FAIL

- [ ] **Step 2: 实现**

在 `backend/app/services/ops/arq_jobs.py` 末尾追加：

```python
def auto_arq_id(task_id: str) -> str:
    return f"auto:{task_id}"


async def enqueue_auto_task(task_id: str) -> str:
    """以稳定 job id 入队自动任务；进行中则直接复用，避免重复执行。"""
    stable_id = auto_arq_id(task_id)
    pool = await _arq_pool()
    settings = get_settings()
    job_probe = Job(stable_id, redis=pool, _queue_name=settings.arq_queue_name)
    st = await job_probe.status()
    if st in _IN_FLIGHT:
        return stable_id
    if st in {JobStatus.complete, JobStatus.not_found}:
        await _clear_arq_job_keys(pool, stable_id)
    job = await pool.enqueue_job(
        "run_auto_schedule_task",
        task_id,
        _job_id=stable_id,
        _queue_name=settings.arq_queue_name,
    )
    if job is None:
        raise RuntimeError(f"enqueue 失败：{task_id}")
    return job.job_id


def enqueue_auto_task_sync(task_id: str) -> str:
    return asyncio.run(enqueue_auto_task(task_id))
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && uv run pytest tests/test_auto_schedule_enqueue.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/ops/arq_jobs.py backend/tests/test_auto_schedule_enqueue.py
git commit -m "feat(worker): 新增自动任务稳定入队函数"
```

---

### Task 5: 服务层与 CRUD API

**Files:**
- Create: `backend/app/services/ops/auto_schedule.py`
- Create: `backend/app/api/v1/auto_schedules.py`
- Modify: `backend/app/api/v1/__init__.py`
- Test: `backend/tests/test_auto_schedules_api.py`

**Interfaces:**
- Consumes: Task 2（`parse_days_of_week`/`parse_times`/`matches_now`）、Task 3（schemas/repo）、Task 4（`enqueue_auto_task_sync`）、`get_builtin_recipe`、`ScreenerRunRepository`、`run_recipe_screen`、`notify_delivery.deliver_text`
- Produces:
  - `validate_task_input(*, name, recipe_id, days_of_week, times) -> None`（非法抛 `ValueError`）
  - `run_task(db, task_id: int) -> SyncResult`
  - `poll_due_tasks(db, now: datetime) -> list[dict[str, str]]`
  - API 路由 `router = APIRouter(prefix="/auto-schedules", ...)`：GET `/`、POST `/`、PATCH `/{id}`、PATCH `/{id}/enabled`、DELETE `/{id}`

- [ ] **Step 1: 写失败 API 测试**（仿 `test_channels_api.py` 的 MagicMock 风格）

```python
# backend/tests/test_auto_schedules_api.py
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User


def _make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=str(uuid4()),
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _api_client(*, db: MagicMock | None = None, user: User | None = None) -> TestClient:
    app = create_app()
    u = user or _make_user()
    session = db if db is not None else MagicMock()

    def override_db():  # type: ignore[no-untyped-def]
        yield session

    def override_user():  # type: ignore[no-untyped-def]
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def _row(*, id_: int = 7) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_,
        user_id="u1",
        name="盘中自动",
        recipe_id="intraday_multi",
        days_of_week="mon-fri",
        times=["09:35", "14:00"],
        enabled=True,
        last_run_at=None,
        last_message=None,
        last_success=None,
        created_at="2026-08-19 10:00:00",
        updated_at="2026-08-19 10:00:00",
    )


def test_list_empty() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    client = _api_client(db=db)
    resp = client.get("/api/v1/auto-schedules")
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []


def test_create_valid() -> None:
    db = MagicMock()
    row = _row()
    with patch(
        "app.repositories.auto_schedule.AutoScheduleRepository.create_task", return_value=row
    ) as create:
        client = _api_client(db=db)
        resp = client.post(
            "/api/v1/auto-schedules",
            json={
                "name": "盘中自动",
                "recipe_id": "intraday_multi",
                "days_of_week": "mon-fri",
                "times": ["09:35", "14:00", "09:35"],
            },
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == 7
    create.assert_called_once()
    assert create.call_args.kwargs["times"] == ["09:35", "14:00"]


def test_create_invalid_recipe() -> None:
    db = MagicMock()
    client = _api_client(db=db)
    resp = client.post(
        "/api/v1/auto-schedules",
        json={"name": "x", "recipe_id": "nope", "days_of_week": "mon-fri", "times": ["09:35"]},
    )
    assert resp.status_code == 400


def test_create_invalid_time() -> None:
    db = MagicMock()
    client = _api_client(db=db)
    resp = client.post(
        "/api/v1/auto-schedules",
        json={"name": "x", "recipe_id": "intraday_multi", "days_of_week": "mon-fri", "times": ["9:35"]},
    )
    assert resp.status_code == 400


def test_update_ok() -> None:
    db = MagicMock()
    row = _row()
    with (
        patch("app.repositories.auto_schedule.AutoScheduleRepository.get", return_value=row),
        patch(
            "app.repositories.auto_schedule.AutoScheduleRepository.update_task", return_value=row
        ) as update,
    ):
        client = _api_client(db=db)
        resp = client.patch("/api/v1/auto-schedules/7", json={"times": ["09:35"]})
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == 7
    assert update.call_args.args == (7, {"times": ["09:35"]})


def test_update_not_found() -> None:
    db = MagicMock()
    with patch("app.repositories.auto_schedule.AutoScheduleRepository.get", return_value=None):
        client = _api_client(db=db)
        resp = client.patch("/api/v1/auto-schedules/99", json={"name": "x"})
    assert resp.status_code == 404


def test_set_enabled() -> None:
    db = MagicMock()
    row = _row()
    row.enabled = False
    with (
        patch("app.repositories.auto_schedule.AutoScheduleRepository.get", return_value=row),
        patch(
            "app.repositories.auto_schedule.AutoScheduleRepository.update_task", return_value=row
        ) as update,
    ):
        client = _api_client(db=db)
        resp = client.patch("/api/v1/auto-schedules/7/enabled", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False
    assert update.call_args.args == (7, {"enabled": False})


def test_delete_ok() -> None:
    db = MagicMock()
    with patch("app.repositories.auto_schedule.AutoScheduleRepository.get", return_value=_row()):
        client = _api_client(db=db)
        resp = client.delete("/api/v1/auto-schedules/7")
    assert resp.status_code == 200
    assert resp.json()["data"]["ok"] is True


def test_delete_not_found() -> None:
    db = MagicMock()
    with patch("app.repositories.auto_schedule.AutoScheduleRepository.get", return_value=None):
        client = _api_client(db=db)
        resp = client.delete("/api/v1/auto-schedules/99")
    assert resp.status_code == 404
```

Run: `cd backend && uv run pytest tests/test_auto_schedules_api.py -v`
Expected: FAIL（API 模块不存在）

- [ ] **Step 2: 实现服务层**

```python
# backend/app/services/ops/auto_schedule.py
"""自动任务：校验、执行与分钟级轮询。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auto_schedule import AutoSchedule
from app.repositories import screener as screener_repo
from app.repositories.auto_schedule import AutoScheduleRepository
from app.schemas.ops import SyncResult
from app.schemas.screener import RecipeRunRequest
from app.services.notify import delivery as notify_delivery
from app.services.ops.arq_jobs import enqueue_auto_task_sync
from app.services.ops.auto_schedule_time import matches_now, parse_days_of_week, parse_times
from app.services.screener.engine import run_recipe_screen
from app.services.screener.presets import get_builtin_recipe

logger = logging.getLogger(__name__)

_META_MESSAGE_MAX = 200


def _now_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def validate_task_input(*, name: str, recipe_id: str, days_of_week: str, times: list[str]) -> None:
    """校验创建/编辑入参；非法抛 ValueError。"""
    if not name.strip():
        raise ValueError("任务名称不能为空")
    recipe = get_builtin_recipe(recipe_id)
    if recipe is None or not recipe.implemented:
        raise ValueError(f"未知或未实现的配方：{recipe_id}")
    parse_days_of_week(days_of_week)
    parse_times(times)


def _record_run(db: Session, task: AutoSchedule, *, message: str, success: bool) -> None:
    task.last_run_at = _now_str()
    task.last_message = str(message)[: _META_MESSAGE_MAX]
    task.last_success = success
    db.commit()


def _notify_result(db: Session, task: AutoSchedule, result: dict[str, Any], run_id: str) -> None:
    from app.services.ops.auto_screen import _format_screen_lines

    text = _format_screen_lines(f"自动任务「{task.name}」", result, run_id)
    notify_delivery.deliver_text(
        db,
        user_id=task.user_id,
        event_type=f"auto_schedule.{task.id}",
        title=f"自动任务：{task.name}",
        text=text,
    )


def run_task(db: Session, task_id: int) -> SyncResult:
    """ARQ worker 执行体：跑配方选股、写历史、更新任务 meta、推送。"""
    repo = AutoScheduleRepository(db, "")
    task = repo.get_any(task_id)
    if task is None:
        return SyncResult(success=False, skipped=True, message="任务不存在")
    if not task.enabled:
        return SyncResult(success=False, skipped=True, message="任务已停用")

    try:
        recipe = get_builtin_recipe(task.recipe_id)
        if recipe is None or not recipe.implemented:
            raise ValueError(f"未知或未实现的配方：{task.recipe_id}")
        req = RecipeRunRequest(recipe_id=task.recipe_id)
        prev = screener_repo.ScreenerRunRepository(db, task.user_id).latest_run_symbols()
        result = run_recipe_screen(req, previous_symbols=prev, db=db, user_id=task.user_id)
        run = screener_repo.ScreenerRunRepository(db, task.user_id).save_run(
            condition=str(result.get("condition") or task.name),
            source="auto_schedule",
            result={**result, "config": {**(result.get("config") or {}), "trigger": f"auto_schedule.{task.id}"}},
        )
    except HTTPException as exc:
        _record_run(db, task, message=str(exc.detail), success=False)
        return SyncResult(success=False, message=str(exc.detail))
    except Exception as exc:
        logger.exception("自动任务执行失败：task=%s", task_id)
        _record_run(db, task, message=str(exc), success=False)
        return SyncResult(success=False, message=str(exc))

    message = f"{task.name}完成：{result.get('condition')} 命中 {result.get('row_count')} 只（run={run.id}）"
    _record_run(db, task, message=message, success=True)
    try:
        _notify_result(db, task, result, run.id)
    except Exception:
        logger.warning("自动任务推送失败：task=%s", task.id, exc_info=True)
    return SyncResult(
        success=True,
        message=message,
        extra={"run_id": run.id, "row_count": result.get("row_count")},
    )


def poll_due_tasks(db: Session, now: datetime) -> list[dict[str, str]]:
    """扫描启用任务，命中当前时刻者入队 ARQ；返回 [{task_id, arq_id}]。"""
    tasks = db.scalars(select(AutoSchedule).where(AutoSchedule.enabled.is_(True))).all()
    due: list[AutoSchedule] = []
    for task in tasks:
        try:
            days = parse_days_of_week(task.days_of_week)
            times = parse_times(list(task.times or []))
        except ValueError:
            logger.warning("自动任务配置非法，跳过：task=%s", task.id)
            continue
        if matches_now(days, times, now):
            due.append(task)
    enqueued: list[dict[str, str]] = []
    for task in due:
        try:
            arq_id = enqueue_auto_task_sync(str(task.id))
        except Exception:
            logger.exception("自动任务入队失败：task=%s", task.id)
            continue
        enqueued.append({"task_id": str(task.id), "arq_id": arq_id})
    return enqueued
```

- [ ] **Step 3: 实现 API**

```python
# backend/app/api/v1/auto_schedules.py
"""自动任务：CRUD + 启用/暂停。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auto_schedule import AutoSchedule
from app.models.user import User
from app.repositories.auto_schedule import AutoScheduleRepository
from app.schemas.auto_schedule import (
    AutoScheduleCreate,
    AutoScheduleEnabledPatch,
    AutoScheduleListOut,
    AutoScheduleOut,
    AutoScheduleUpdate,
)
from app.schemas.common import ApiResponse, OkOut
from app.services.ops.auto_schedule import validate_task_input
from app.services.ops.auto_schedule_time import parse_times

router = APIRouter(prefix="/auto-schedules", tags=["auto-schedules"])


def _get_owned(
    db: Session, user_id: str, task_id: int
) -> tuple[AutoScheduleRepository, AutoSchedule]:
    repo = AutoScheduleRepository(db, user_id)
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return repo, task


@router.get("", response_model=ApiResponse[AutoScheduleListOut])
def list_auto_schedules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleListOut]:
    repo = AutoScheduleRepository(db, str(user.id))
    tasks = repo.list_all()
    return ApiResponse(data=AutoScheduleListOut(items=[repo.to_out(t) for t in tasks]))


@router.post("", response_model=ApiResponse[AutoScheduleOut])
def create_auto_schedule(
    body: AutoScheduleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleOut]:
    repo = AutoScheduleRepository(db, str(user.id))
    try:
        validate_task_input(
            name=body.name,
            recipe_id=body.recipe_id,
            days_of_week=body.days_of_week,
            times=body.times,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    task = repo.create_task(
        name=body.name.strip(),
        recipe_id=body.recipe_id,
        days_of_week=body.days_of_week.strip().lower(),
        times=parse_times(body.times),
    )
    return ApiResponse(data=repo.to_out(task))


@router.patch("/{task_id}", response_model=ApiResponse[AutoScheduleOut])
def update_auto_schedule(
    task_id: int,
    body: AutoScheduleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleOut]:
    repo, task = _get_owned(db, str(user.id), task_id)
    values = body.model_dump(exclude_none=True)
    if not values:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    try:
        validate_task_input(
            name=values.get("name", task.name),
            recipe_id=values.get("recipe_id", task.recipe_id),
            days_of_week=values.get("days_of_week", task.days_of_week),
            times=values.get("times", list(task.times or [])),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "name" in values:
        values["name"] = str(values["name"]).strip()
    if "days_of_week" in values:
        values["days_of_week"] = str(values["days_of_week"]).strip().lower()
    if "times" in values:
        values["times"] = parse_times(values["times"])
    updated = repo.update_task(task_id, values)
    if updated is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(data=repo.to_out(updated))


@router.patch("/{task_id}/enabled", response_model=ApiResponse[AutoScheduleOut])
def set_auto_schedule_enabled(
    task_id: int,
    body: AutoScheduleEnabledPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleOut]:
    repo, _ = _get_owned(db, str(user.id), task_id)
    updated = repo.update_task(task_id, {"enabled": body.enabled})
    if updated is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(data=repo.to_out(updated))


@router.delete("/{task_id}", response_model=ApiResponse[OkOut])
def delete_auto_schedule(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    repo, _ = _get_owned(db, str(user.id), task_id)
    repo.delete(task_id)
    return ApiResponse(data=OkOut())
```

- [ ] **Step 4: 注册路由**

```python
# backend/app/api/v1/__init__.py —— import 区加 auto_schedules
from app.api.v1 import ai, auth, auto_schedules, backtest, channels, content, jobs, market, ops, screener, watchlist, ws
# include_router 区加一行
api_router.include_router(auto_schedules.router)
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && uv run pytest tests/test_auto_schedules_api.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/ops/auto_schedule.py backend/app/api/v1/auto_schedules.py backend/app/api/v1/__init__.py backend/tests/test_auto_schedules_api.py
git commit -m "feat(api): 新增自动任务 CRUD 与启停接口"
```

---

### Task 6: Worker 执行任务

**Files:**
- Create: `backend/app/worker/tasks_auto_schedule.py`
- Modify: `backend/app/worker/settings.py`
- Test: `backend/tests/test_auto_schedule_task.py`

**Interfaces:**
- Consumes: Task 5 `run_task(db, task_id)`、`SessionLocal`
- Produces: `worker.tasks_auto_schedule.run_auto_schedule_task(ctx, *, task_id: str) -> dict`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_auto_schedule_task.py
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.schemas.ops import SyncResult
from app.services.ops.auto_schedule import run_task
from app.worker.tasks_auto_schedule import run_auto_schedule_task


def _task(*, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        user_id="u1",
        name="盘中自动",
        recipe_id="intraday_multi",
        days_of_week="mon-fri",
        times=["09:35"],
        enabled=enabled,
        last_run_at=None,
        last_message=None,
        last_success=None,
    )


def test_run_task_missing() -> None:
    db = MagicMock()
    with patch("app.repositories.auto_schedule.AutoScheduleRepository.get_any", return_value=None):
        out = run_task(db, 99)
    assert out.success is False
    assert out.skipped is True


def test_run_task_disabled() -> None:
    db = MagicMock()
    with patch(
        "app.repositories.auto_schedule.AutoScheduleRepository.get_any", return_value=_task(enabled=False)
    ):
        out = run_task(db, 7)
    assert out.success is False
    assert out.skipped is True


def test_run_task_success() -> None:
    db = MagicMock()
    fake_result = {
        "condition": "盘中多因子",
        "row_count": 2,
        "total_scanned": 10,
        "config": {},
        "rows": [],
    }
    fake_run = MagicMock(id="run-a")
    task = _task()
    with (
        patch("app.repositories.auto_schedule.AutoScheduleRepository.get_any", return_value=task),
        patch("app.repositories.screener.ScreenerRunRepository.latest_run_symbols", return_value=None),
        patch("app.services.ops.auto_schedule.run_recipe_screen", return_value=fake_result),
        patch("app.repositories.screener.ScreenerRunRepository.save_run", return_value=fake_run) as save,
        patch("app.services.ops.auto_schedule.notify_delivery.deliver_text") as deliver,
    ):
        out = run_task(db, 7)
    assert out.success is True
    assert out.extra["run_id"] == "run-a"
    assert task.last_success is True
    assert "盘中多因子" in task.last_message
    save.assert_called_once()
    assert save.call_args.kwargs["source"] == "auto_schedule"
    deliver.assert_called_once()
    assert deliver.call_args.kwargs["user_id"] == "u1"
    assert deliver.call_args.kwargs["event_type"] == "auto_schedule.7"


def test_run_task_unknown_recipe() -> None:
    db = MagicMock()
    task = _task()
    task.recipe_id = "nope"
    with (
        patch("app.repositories.auto_schedule.AutoScheduleRepository.get_any", return_value=task),
        patch("app.services.ops.auto_schedule.run_recipe_screen"),
    ):
        out = run_task(db, 7)
    assert out.success is False
    assert task.last_success is False
    assert "未知" in task.last_message


def test_run_task_push_failure_does_not_raise() -> None:
    db = MagicMock()
    fake_result = {"condition": "盘中多因子", "row_count": 0, "total_scanned": 10, "config": {}, "rows": []}
    fake_run = MagicMock(id="run-b")
    task = _task()
    with (
        patch("app.repositories.auto_schedule.AutoScheduleRepository.get_any", return_value=task),
        patch("app.repositories.screener.ScreenerRunRepository.latest_run_symbols", return_value=None),
        patch("app.services.ops.auto_schedule.run_recipe_screen", return_value=fake_result),
        patch("app.repositories.screener.ScreenerRunRepository.save_run", return_value=fake_run),
        patch(
            "app.services.ops.auto_schedule.notify_delivery.deliver_text",
            side_effect=Exception("db down"),
        ),
    ):
        out = run_task(db, 7)
    assert out.success is True


def test_worker_task_returns_dict() -> None:
    async def _go() -> dict:
        with patch(
            "app.worker.tasks_auto_schedule.ops_auto_schedule.run_task",
            return_value=SyncResult(success=True, message="ok"),
        ):
            return await run_auto_schedule_task({}, task_id="7")

    out = asyncio.run(_go())
    assert out["success"] is True
```

Run: `cd backend && uv run pytest tests/test_auto_schedule_task.py -v`
Expected: FAIL

- [ ] **Step 2: 实现 worker 任务**

```python
# backend/app/worker/tasks_auto_schedule.py
"""ARQ：自动任务执行。"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.db import SessionLocal
from app.services.ops import auto_schedule as ops_auto_schedule


def _run(task_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        result = ops_auto_schedule.run_task(db, task_id)
        return result.model_dump()
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    finally:
        db.close()


async def run_auto_schedule_task(ctx: dict, *, task_id: str) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run, task_id)
```

- [ ] **Step 3: 注册 worker 函数**

```python
# backend/app/worker/settings.py —— import 区加一行
from app.worker.tasks_auto_schedule import run_auto_schedule_task
# functions 列表末尾追加
run_auto_schedule_task,
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && uv run pytest tests/test_auto_schedule_task.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/worker/tasks_auto_schedule.py backend/app/worker/settings.py backend/tests/test_auto_schedule_task.py
git commit -m "feat(worker): 新增自动任务 ARQ 执行"
```

---

### Task 7: 内嵌调度器守护轮询

**Files:**
- Modify: `backend/app/services/ops/embedded_scheduler.py`
- Test: `backend/tests/test_auto_schedule_poll.py`

**Interfaces:**
- Consumes: Task 5 `poll_due_tasks(db, now)`、`china_now`、`scheduler_lock`
- Produces: `embedded_scheduler.poll_auto_schedule()`（每分钟轮询；start_embedded_scheduler 中注册 id=`auto_schedule_poll` 的 CronTrigger(minute="*") job）

- [ ] **Step 1: 写失败测试**（仿 `test_embedded_scheduler_enqueue.py`）

```python
# backend/tests/test_auto_schedule_poll.py
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from app.core.time import CHINA_TZ
from app.services.ops import embedded_scheduler as es

MON_0935 = datetime(2026, 8, 17, 9, 35, tzinfo=CHINA_TZ)


def _settings(enabled: bool = True) -> MagicMock:
    s = MagicMock()
    s.scheduler_effective_enabled = enabled
    return s


def test_poll_auto_schedule_enqueues_due() -> None:
    with (
        patch.object(es, "get_settings", return_value=_settings()),
        patch.object(es.scheduler_lock, "try_acquire", return_value=True),
        patch.object(es.scheduler_lock, "release"),
        patch.object(es.scheduler_lock, "make_token", return_value="t"),
        patch.object(es, "SessionLocal") as SL,
        patch(
            "app.services.ops.auto_schedule.poll_due_tasks",
            return_value=[{"task_id": "7", "arq_id": "auto:7"}],
        ) as poll,
        patch("app.core.time.china_now", return_value=MON_0935),
    ):
        SL.return_value = MagicMock()
        es.poll_auto_schedule()
    poll.assert_called_once()
    assert poll.call_args.args[1] == MON_0935


def test_poll_auto_schedule_skips_when_disabled() -> None:
    with (
        patch.object(es, "get_settings", return_value=_settings(False)),
        patch("app.services.ops.auto_schedule.poll_due_tasks") as poll,
    ):
        es.poll_auto_schedule()
    poll.assert_not_called()
```

Run: `cd backend && uv run pytest tests/test_auto_schedule_poll.py -v`
Expected: FAIL

- [ ] **Step 2: 实现守护轮询**

在 `backend/app/services/ops/embedded_scheduler.py` 中：

- import 区加：

```python
from app.core.time import china_now
from app.services.ops import auto_schedule as ops_auto_schedule
```

- 新增函数：

```python
def poll_auto_schedule() -> None:
    settings = get_settings()
    if not settings.scheduler_effective_enabled:
        return
    token = scheduler_lock.make_token()
    if not scheduler_lock.try_acquire("auto_schedule_poll", token=token):
        return
    db = SessionLocal()
    try:
        ops_auto_schedule.poll_due_tasks(db, china_now())
    finally:
        scheduler_lock.release("auto_schedule_poll", token)
        db.close()
```

- 在 `start_embedded_scheduler()` 中，`sched.start()` 之前追加：

```python
    sched.add_job(
        poll_auto_schedule,
        CronTrigger(minute="*"),
        id="auto_schedule_poll",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && uv run pytest tests/test_auto_schedule_poll.py tests/test_embedded_scheduler_enqueue.py -v`
Expected: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/ops/embedded_scheduler.py backend/tests/test_auto_schedule_poll.py
git commit -m "feat(ops): 内嵌调度新增自动任务分钟级守护轮询"
```

---

### Task 8: 前端 API 与页面

**Files:**
- Create: `frontend/src/api/autoSchedule.ts`
- Create: `frontend/src/views/AutoScheduleView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/AppShell.vue`
- Modify: `frontend/src/components/NavIcon.vue`

**Interfaces:**
- Consumes: `channelApi` 页面风格、`confirmDialog`、`screenerApi.builtinRecipes`
- Produces: `autoScheduleApi`（list/create/update/setEnabled/remove）、路由 `/auto-schedule`、导航项「自动任务」

- [ ] **Step 1: 实现 API 封装**

```typescript
// frontend/src/api/autoSchedule.ts
import { api } from './client'

export type AutoSchedule = {
  id: number
  name: string
  recipe_id: string
  days_of_week: string
  times: string[]
  enabled: boolean
  last_run_at: string | null
  last_message: string | null
  last_success: boolean | null
  created_at: string
  updated_at: string
}

export type AutoScheduleBody = {
  name: string
  recipe_id: string
  days_of_week: string
  times: string[]
}

export const autoScheduleApi = {
  list: () => api<{ items: AutoSchedule[] }>('/api/v1/auto-schedules'),
  create: (body: AutoScheduleBody) =>
    api<AutoSchedule>('/api/v1/auto-schedules', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  update: (id: number, body: Partial<AutoScheduleBody>) =>
    api<AutoSchedule>(`/api/v1/auto-schedules/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  setEnabled: (id: number, enabled: boolean) =>
    api<AutoSchedule>(`/api/v1/auto-schedules/${id}/enabled`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),
  remove: (id: number) =>
    api<{ ok: boolean }>(`/api/v1/auto-schedules/${id}`, {
      method: 'DELETE',
    }),
}
```

- [ ] **Step 2: 实现页面组件**

```vue
<!-- frontend/src/views/AutoScheduleView.vue -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import { autoScheduleApi, type AutoSchedule } from '../api/autoSchedule'
import { screenerApi, type BuiltinRecipe } from '../api/screener'
import { confirmDialog } from '../lib/dialog'

const items = ref<AutoSchedule[]>([])
const recipes = ref<BuiltinRecipe[]>([])
const loading = ref(false)
const loaded = ref(false)
const error = ref('')

const bannerMsg = ref('')
const bannerKind = ref<'ok' | 'err'>('ok')

const editorOpen = ref(false)
const editorSaving = ref(false)
const editorErr = ref('')
const editingId = ref<number | null>(null)
const formName = ref('')
const formRecipe = ref('')
const formDays = ref<string[]>(['mon', 'tue', 'wed', 'thu', 'fri'])
const formTimes = ref<string[]>(['09:35'])

const DAY_OPTIONS = [
  { key: 'mon', label: '周一' },
  { key: 'tue', label: '周二' },
  { key: 'wed', label: '周三' },
  { key: 'thu', label: '周四' },
  { key: 'fri', label: '周五' },
  { key: 'sat', label: '周六' },
  { key: 'sun', label: '周日' },
]

const DAY_LABEL: Record<string, string> = Object.fromEntries(
  DAY_OPTIONS.map((d) => [d.key, d.label]),
)

function banner(kind: 'ok' | 'err', msg: string) {
  bannerKind.value = kind
  bannerMsg.value = msg
}

function recipeName(recipeId: string): string {
  return recipes.value.find((r) => r.recipe_id === recipeId)?.name || recipeId
}

function scheduleText(t: AutoSchedule): string {
  const dayText = t.days_of_week
    .split(',')
    .map((d) => DAY_LABEL[d] || d)
    .join('·')
  return `${dayText} ${t.times.join('、')}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    items.value = (await autoScheduleApi.list()).items
    loaded.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : '任务列表加载失败'
  } finally {
    loading.value = false
  }
}

async function loadRecipes() {
  try {
    recipes.value = (await screenerApi.builtinRecipes()).filter((r) => r.implemented)
    if (!formRecipe.value && recipes.value.length) {
      formRecipe.value = recipes.value[0].recipe_id
    }
  } catch {
    /* 配方加载失败静默，保存时后端会校验 */
  }
}

function openCreate() {
  editingId.value = null
  formName.value = ''
  formRecipe.value = recipes.value[0]?.recipe_id || ''
  formDays.value = ['mon', 'tue', 'wed', 'thu', 'fri']
  formTimes.value = ['09:35']
  editorErr.value = ''
  editorOpen.value = true
}

function openEdit(t: AutoSchedule) {
  editingId.value = t.id
  formName.value = t.name
  formRecipe.value = t.recipe_id
  formDays.value = t.days_of_week.split(',')
  formTimes.value = [...t.times]
  editorErr.value = ''
  editorOpen.value = true
}

function addTimeRow() {
  formTimes.value = [...formTimes.value, '']
}

function removeTimeRow(index: number) {
  formTimes.value = formTimes.value.filter((_, i) => i !== index)
}

async function saveEditor() {
  const name = formName.value.trim()
  const days = formDays.value.join(',')
  const times = formTimes.value
    .map((t) => t.trim())
    .filter((t) => t !== '')
    .sort()
  const deduped = [...new Set(times)]
  if (!name) {
    editorErr.value = '请填写任务名称'
    return
  }
  if (formDays.value.length === 0) {
    editorErr.value = '请至少选择一天'
    return
  }
  if (deduped.length === 0) {
    editorErr.value = '请至少填写一个执行时刻'
    return
  }
  if (deduped.some((t) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(t))) {
    editorErr.value = '时刻格式应为 HH:MM，如 09:35'
    return
  }
  editorSaving.value = true
  editorErr.value = ''
  const body = { name, recipe_id: formRecipe.value, days_of_week: days, times: deduped }
  try {
    if (editingId.value != null) {
      await autoScheduleApi.update(editingId.value, body)
    } else {
      await autoScheduleApi.create(body)
    }
    editorOpen.value = false
    banner('ok', editingId.value != null ? '任务已更新' : '任务已创建')
    void load()
  } catch (e) {
    editorErr.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    editorSaving.value = false
  }
}

async function toggleEnabled(t: AutoSchedule) {
  try {
    await autoScheduleApi.setEnabled(t.id, !t.enabled)
    void load()
  } catch (e) {
    banner('err', e instanceof Error ? e.message : '切换失败')
  }
}

async function removeTask(t: AutoSchedule) {
  const ok = await confirmDialog({
    title: '删除任务',
    message: `确认删除「${t.name}」？删除后不再定时执行。`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await autoScheduleApi.remove(t.id)
    banner('ok', '任务已删除')
    void load()
  } catch (e) {
    banner('err', e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(() => {
  void loadRecipes()
  void load()
})

const empty = computed(
  () => loaded.value && !loading.value && !error.value && items.value.length === 0,
)
</script>

<template>
  <AppShell
    title="自动任务"
    subtitle="创建选股任务：选择配方与执行时刻，到点自动跑选股并推送已启用渠道。"
    active="auto-schedule"
  >
    <div class="page">
      <div class="toolbar">
        <div>
          <h2>我的自动任务</h2>
          <p class="muted">按用户隔离；任务按「星期 + 时刻」分钟级触发，不补跑错过的时刻。</p>
        </div>
        <div class="actions">
          <button type="button" class="primary" @click="openCreate">+ 新建任务</button>
          <button type="button" class="ghost" :disabled="loading" @click="load">
            {{ loading ? '加载中…' : '刷新' }}
          </button>
        </div>
      </div>

      <Transition name="fade">
        <div v-if="bannerMsg" class="banner" :class="bannerKind">
          {{ bannerMsg }}
          <button type="button" class="banner-close" aria-label="关闭" @click="bannerMsg = ''">
            ×
          </button>
        </div>
      </Transition>

      <p v-if="loading && !loaded" class="muted">加载任务列表…</p>
      <p v-else-if="error" class="err">{{ error }}</p>
      <template v-else>
        <div v-if="items.length" class="task-list">
          <div v-for="t in items" :key="t.id" class="task-card" :class="{ off: !t.enabled }">
            <div class="card-head">
              <div class="card-title">
                <span class="name">{{ t.name }}</span>
                <span class="badge">{{ recipeName(t.recipe_id) }}</span>
                <span v-if="!t.enabled" class="badge off">已停用</span>
              </div>
              <label class="switch" :title="t.enabled ? '停用' : '启用'">
                <input type="checkbox" :checked="t.enabled" @change="toggleEnabled(t)" />
                <span class="slider" />
              </label>
            </div>
            <div class="schedule">{{ scheduleText(t) }}</div>
            <div class="last-run">
              <template v-if="t.last_run_at">
                <span :class="t.last_success === false ? 'err' : t.last_success ? 'ok-text' : ''">
                  {{ t.last_success === false ? '失败' : t.last_success ? '成功' : '—' }}
                </span>
                <span class="muted">· {{ t.last_run_at }}</span>
                <div v-if="t.last_message" class="muted msg">{{ t.last_message }}</div>
              </template>
              <span v-else class="muted">尚未执行</span>
            </div>
            <div class="card-actions">
              <button type="button" class="ghost" @click="openEdit(t)">编辑</button>
              <button type="button" class="ghost danger" @click="removeTask(t)">删除</button>
            </div>
          </div>
        </div>
        <div v-else-if="empty" class="empty">
          <p>还没有创建任何自动任务。</p>
          <button type="button" class="primary" @click="openCreate">+ 新建任务</button>
        </div>
      </template>
    </div>
  </AppShell>

  <Teleport to="body">
    <Transition name="fade">
      <div v-if="editorOpen" class="overlay" @click.self="editorOpen = false">
        <div class="editor" role="dialog" aria-modal="true">
          <h3 class="editor-title">{{ editingId != null ? '编辑任务' : '新建任务' }}</h3>
          <label class="field">
            <span class="field-label">任务名称</span>
            <input v-model="formName" class="input-field" placeholder="例如：盘中自动选股" maxlength="64" />
          </label>
          <label class="field">
            <span class="field-label">选股配方</span>
            <select v-model="formRecipe" class="input-field">
              <option v-for="r in recipes" :key="r.recipe_id" :value="r.recipe_id">
                {{ r.name }}
              </option>
            </select>
          </label>
          <div class="field">
            <span class="field-label">每周执行日</span>
            <div class="day-row">
              <label v-for="d in DAY_OPTIONS" :key="d.key" class="day-chip">
                <input v-model="formDays" type="checkbox" :value="d.key" />
                <span>{{ d.label }}</span>
              </label>
            </div>
          </div>
          <div class="field">
            <span class="field-label">执行时刻（每天）</span>
            <div v-for="(_, i) in formTimes" :key="i" class="time-row">
              <input v-model="formTimes[i]" class="input-field time-input" placeholder="HH:MM" maxlength="5" />
              <button type="button" class="ghost small" :disabled="formTimes.length <= 1" @click="removeTimeRow(i)">
                删除
              </button>
            </div>
            <button type="button" class="ghost small" @click="addTimeRow">+ 添加时刻</button>
          </div>
          <p v-if="editorErr" class="err">{{ editorErr }}</p>
          <div class="editor-actions">
            <button type="button" class="ghost" :disabled="editorSaving" @click="editorOpen = false">
              取消
            </button>
            <button type="button" class="primary" :disabled="editorSaving" @click="saveEditor">
              {{ editorSaving ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.page {
  display: grid;
  gap: 16px;
}
.toolbar h2 {
  margin: 0;
  font-size: 1rem;
}
.actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-radius: 0.625rem;
  padding: 0.6rem 0.85rem;
  font-size: 0.875rem;
}
.banner.ok {
  background: #f0fdf4;
  color: var(--ok);
  border: 1px solid #bbf7d0;
}
.banner.err {
  background: #fef2f2;
  color: var(--danger);
  border: 1px solid #fecaca;
}
.banner-close {
  border: none;
  background: transparent;
  color: inherit;
  font-size: 1rem;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 0.375rem;
}
.task-list {
  display: grid;
  gap: 12px;
}
.task-card {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  padding: 12px 14px;
  display: grid;
  gap: 8px;
}
.task-card.off {
  opacity: 0.6;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.name {
  font-weight: 600;
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background: #eef2ff;
  color: #4338ca;
}
.badge.off {
  background: #f1f5f9;
  color: #64748b;
}
.schedule {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.875rem;
}
.last-run {
  font-size: 0.8125rem;
}
.msg {
  margin-top: 2px;
  word-break: break-all;
}
.card-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.muted {
  color: var(--muted);
  font-size: 0.78rem;
}
.err {
  color: var(--danger);
}
.ok-text {
  color: var(--ok);
}
.empty {
  border: 1px dashed var(--line);
  border-radius: 0.75rem;
  padding: 40px;
  text-align: center;
  color: var(--muted);
  display: grid;
  gap: 12px;
  justify-items: center;
}
.switch {
  position: relative;
  display: inline-flex;
  cursor: pointer;
}
.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  width: 40px;
  height: 22px;
  border-radius: 999px;
  background: var(--line);
  position: relative;
  transition: background 0.2s ease;
}
.slider::before {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #fff;
  top: 2px;
  left: 2px;
  transition: transform 0.2s ease;
}
.switch input:checked + .slider {
  background: var(--ok);
}
.switch input:checked + .slider::before {
  transform: translateX(18px);
}
.day-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.day-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.8125rem;
  cursor: pointer;
}
.time-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  align-items: center;
}
.time-input {
  max-width: 120px;
}
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: grid;
  place-items: center;
  z-index: 50;
}
.editor {
  width: min(480px, 92vw);
  max-height: 88vh;
  overflow: auto;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.875rem;
  padding: 20px;
  display: grid;
  gap: 14px;
}
.editor-title {
  margin: 0;
  font-size: 1rem;
}
.field {
  display: grid;
  gap: 6px;
}
.field-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--ink-muted);
}
.input-field {
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--line);
  background: var(--bg);
  color: var(--ink);
  font-size: 0.875rem;
}
.editor-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.primary,
.ghost {
  border-radius: 0.5rem;
  padding: 8px 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  font-size: 0.875rem;
}
.primary {
  background: var(--accent);
  border-color: transparent;
  color: var(--brand-foreground);
  font-weight: 600;
}
.ghost {
  background: var(--bg);
  color: var(--text);
}
.ghost.small {
  padding: 4px 8px;
  font-size: 0.8125rem;
}
.ghost.danger {
  color: var(--danger);
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
```

- [ ] **Step 3: 注册路由**

```typescript
// frontend/src/router/index.ts —— 在 /channels 行后追加
{
  path: '/auto-schedule',
  name: 'auto-schedule',
  component: () => import('../views/AutoScheduleView.vue'),
},
```

- [ ] **Step 4: 添加导航项**

```typescript
// frontend/src/components/AppShell.vue
// active 类型与 NavKey 联合类型各加 'auto-schedule'
// 「系统」分组 items 中 channels 之前加：
{ key: 'auto-schedule', label: '自动任务', to: '/auto-schedule', enabled: true },
```

```typescript
// frontend/src/components/NavIcon.vue
// NavIconName 联合类型加 'auto-schedule'
// paths 加一项（循环箭头图标）：
auto-schedule: ['M4.5 12a7.5 7.5 0 0115 0m-15 0l3 3m-3-3l3-3m7.5 0h3m-3 0l-3-3'],
```

- [ ] **Step 5: 构建验证**

Run: `cd frontend && npm run build`
Expected: `vue-tsc` + `vite build` 通过

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/autoSchedule.ts frontend/src/views/AutoScheduleView.vue frontend/src/router/index.ts frontend/src/components/AppShell.vue frontend/src/components/NavIcon.vue
git commit -m "feat(ui): 新增自动任务页面与侧边栏入口"
```

---

### Task 9: 全量回归

**Files:**
- 无新文件

- [ ] **Step 1: 后端全量测试 + lint**

Run: `cd backend && uv run pytest -q`
Expected: 全部 PASS（新增约 35 个测试）

Run: `cd backend && uv run ruff check app tests`
Expected: 无报错

Run: `cd backend && uv run mypy app`
Expected: 无报错

- [ ] **Step 2: 前端构建 + lint**

Run: `cd frontend && npm run build && npm run lint:check`
Expected: 通过

- [ ] **Step 3: 完整 check**

Run: `./scripts/check.sh`
Expected: 全部通过

- [ ] **Step 4: 手工冒烟（可选）**

1. 启动 `./scripts/dev.sh`
2. 前端登录 → 「系统 → 自动任务」→ 新建任务（配方盘中多因子、周一~周五、09:35、14:00）
3. 等待命中时刻 → 检查任务卡片「上次运行」更新、`screener_runs` 新增 `auto_schedule` 记录
4. 停用/编辑/删除任务验证
