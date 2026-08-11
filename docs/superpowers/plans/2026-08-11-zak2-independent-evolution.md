# zak2 独立演进 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** zak2 默认自有 PostgreSQL + Redis + Alembic，Redis 行情键改用 `zak2:`，去掉对 zak CLI/同库的依赖，并提供可选一次性导入与产品文档解绑。

**Architecture:** Compose 编入 postgres/redis；从兄弟仓库 zak 拷贝 DDL 作为初始 Alembic（不 import `vnpy_*`）；统一 `app.core.redis_keys.KEY_PREFIX = "zak2"`；Ops 未实现 job 标为 planned；`scripts/import_from_zak.py` 做 truncate-then-copy。

**Tech Stack:** FastAPI、SQLAlchemy 2、Alembic、psycopg、Redis、Docker Compose、Vue3、pytest

**Spec:** `docs/superpowers/specs/2026-08-11-zak2-independent-evolution-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-* 源码（允许**只读拷贝** zak 的 `alembic/ddl` 与 versions 到本仓）
- 不 import `vnpy_*`
- Redis 行情/排行/meta/notify 前缀必须为 `zak2`（不再读写 `zak:quote:*` 等）
- 默认 `DATABASE_URL` 库名 `zak2`；导入源用单独变量 `ZAK_IMPORT_DATABASE_URL`
- 不把 `collect_quotes` 加入 `RUNNABLE_JOB_IDS`
- commit message 简体中文：`<type>(<scope>): <简述>`
- 顺序：P0 骨架 → P1 前缀 → P3 文档/Ops → P2 导入（绿场可跳过 P2）

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/core/redis_keys.py` | 唯一 `KEY_PREFIX` 与行情相关键常量 |
| `backend/alembic/` + `backend/alembic.ini` | 迁库主权 |
| `backend/scripts/docker-entrypoint.sh` | Compose 内 upgrade 后启 uvicorn |
| `docker-compose.yml` | postgres/redis/api/collector/web |
| `scripts/import_from_zak.py` | 一次性导入 |
| `docs/product-roadmap.md` / `docs/archive/gap-vs-desktop.md` | 产品文档 |

---

### Task 1: 统一 Redis 前缀为 `zak2`

**Files:**
- Create: `backend/app/core/redis_keys.py`
- Modify: `backend/app/services/quotes.py`
- Modify: `backend/app/services/quote_collect/writer.py`
- Modify: `backend/app/services/quote_notify_hub.py`
- Modify: `backend/app/services/strategy_board.py`
- Modify: `backend/app/api/v1/ws.py`
- Modify: `backend/tests/test_quote_collect_writer.py`
- Test: `backend/tests/test_redis_keys.py`

**Interfaces:**
- Produces: `app.core.redis_keys.KEY_PREFIX == "zak2"`；`NOTIFY_CHANNEL == "zak2:notify:quotes"`；`QUOTE_KEY_FMT` / `RANK_KEY_FMT` / meta keys

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_redis_keys.py`:

```python
from app.core import redis_keys


def test_key_prefix_is_zak2() -> None:
    assert redis_keys.KEY_PREFIX == "zak2"
    assert redis_keys.NOTIFY_CHANNEL == "zak2:notify:quotes"
    assert redis_keys.QUOTE_KEY_FMT.format(symbol="SHSE.600519") == "zak2:quote:SHSE.600519"
    assert "zak:" not in redis_keys.NOTIFY_CHANNEL.replace("zak2:", "")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_redis_keys.py -v`  
Expected: FAIL（`ModuleNotFoundError` 或 import 失败）

- [ ] **Step 3: 实现 `redis_keys.py` 并改引用**

`backend/app/core/redis_keys.py`:

```python
"""zak2 Redis 键常量（行情 / 排行 / 通知）。"""

from __future__ import annotations

KEY_PREFIX = "zak2"
RANK_KEY_FMT = f"{KEY_PREFIX}:rank:{{field}}"
QUOTE_KEY_FMT = f"{KEY_PREFIX}:quote:{{symbol}}"
QUOTE_BLOB_KEY_FMT = f"{KEY_PREFIX}:quote:b:{{symbol}}"
META_UPDATED_AT_KEY = f"{KEY_PREFIX}:meta:updated_at"
META_QUOTE_COUNT_KEY = f"{KEY_PREFIX}:meta:quote_count"
META_SEQ_KEY = f"{KEY_PREFIX}:meta:seq"
NOTIFY_CHANNEL = f"{KEY_PREFIX}:notify:quotes"
```

在 `quotes.py`、`quote_collect/writer.py`：删除本地 `KEY_PREFIX = "zak"` 及派生常量，改为：

```python
from app.core.redis_keys import (
    KEY_PREFIX,
    META_QUOTE_COUNT_KEY,
    META_SEQ_KEY,  # writer only
    META_UPDATED_AT_KEY,
    NOTIFY_CHANNEL,  # writer only
    QUOTE_BLOB_KEY_FMT,  # quotes only
    QUOTE_KEY_FMT,
    RANK_KEY_FMT,
)
```

`quote_notify_hub.py`：

```python
from app.core.redis_keys import NOTIFY_CHANNEL as QUOTE_NOTIFY_CHANNEL
```

（或直接使用 `NOTIFY_CHANNEL`，同步改文件内引用。）

`strategy_board.py`：`from app.core.redis_keys import KEY_PREFIX`

`ws.py` hello：

```python
from app.core.redis_keys import NOTIFY_CHANNEL
# ...
await websocket.send_json({"type": "hello", "channel": NOTIFY_CHANNEL})
```

`test_quote_collect_writer.py`：`assert_called_with("zak2:notify:quotes", "7")`

更新 `quotes.py` / `writer.py` / `quote_notify_hub.py` 模块 docstring，去掉「兼容 zak 键名」表述，改为「zak2 自有键」。

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
cd backend && uv run pytest tests/test_redis_keys.py tests/test_quote_collect_writer.py tests/test_quote_ws.py tests/test_quote_collect_loop.py -q
```

Expected: PASS

再扫残留：

```bash
cd backend && rg -n 'KEY_PREFIX\s*=\s*"zak"|zak:notify:quotes|zak:quote:' app tests
```

Expected: 无业务硬编码（注释/历史字符串除外；若有则改掉）

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/redis_keys.py backend/app/services/quotes.py \
  backend/app/services/quote_collect/writer.py backend/app/services/quote_notify_hub.py \
  backend/app/services/strategy_board.py backend/app/api/v1/ws.py \
  backend/tests/test_redis_keys.py backend/tests/test_quote_collect_writer.py
git commit -m "$(cat <<'EOF'
refactor(redis): 行情键前缀统一为 zak2

拆库后不再兼容桌面 zak: 键，读写与通知共用同一常量。
EOF
)"
```

---

### Task 2: 默认连 zak2 库（settings + .env.example）

**Files:**
- Modify: `backend/app/core/settings.py`
- Modify: `.env.example`
- Test: `backend/tests/test_settings_defaults.py`

**Interfaces:**
- Produces: 默认 `database_url` 含 `/zak2`；settings 可增加只读字段说明导入 URL 不由 API 使用（导入脚本读 os.environ）

- [ ] **Step 1: 写失败测试**

```python
from app.core.settings import Settings


def test_default_database_targets_zak2() -> None:
    s = Settings(_env_file=None)
    assert "/zak2" in s.database_url
    assert s.database_url.endswith("/zak2") or "/zak2?" in s.database_url
```

（若 `Settings` 仍从环境读到旧值，测试里用 `Settings(database_url="postgresql+psycopg://zak2:zak2@localhost:5432/zak2")` 验证字段可设；默认值断言用：

```python
assert Settings.model_fields["database_url"].default.endswith("/zak2")
```

）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_settings_defaults.py -v`  
Expected: FAIL

- [ ] **Step 3: 改默认值与 .env.example**

`settings.py`：

```python
database_url: str = "postgresql+psycopg://zak2:zak2@localhost:5432/zak2"
redis_url: str = "redis://127.0.0.1:6379/0"
```

`.env.example` 全文替换头部为：

```bash
# zak2 自有 PostgreSQL（先 alembic upgrade；勿默认连桌面 zak 库）
DATABASE_URL=postgresql+psycopg://zak2:zak2@localhost:5432/zak2

# 可选：一次性从旧 zak 库导入（仅 scripts/import_from_zak.py 使用）
# ZAK_IMPORT_DATABASE_URL=postgresql+psycopg://zak:zak@localhost:5432/zak

JWT_SECRET=change-me-in-production-min-32-chars!!
JWT_EXPIRE_DAYS=7

REDIS_URL=redis://127.0.0.1:6379/0

# 行情采集（本实例内只跑一个 collector）
TICKFLOW_API_KEY=
QUOTE_PROVIDER=tickflow
QUOTE_COLLECT_INTERVAL_SEC=30
QUOTE_COLLECTOR_ENABLED=true
```

删除「与 zak 共用」「勿与 zak CLI 双写」「DOCKER_* 默认 host.docker.internal→zak」等旧注释；Compose 相关改为指向服务名 `postgres`/`redis`（Task 5 会写死 environment）。

保留其余 LLM/MCP/CORS/调度段，仅改库相关表述。

- [ ] **Step 4: 跑测试**

Run: `cd backend && uv run pytest tests/test_settings_defaults.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/settings.py backend/tests/test_settings_defaults.py .env.example
git commit -m "$(cat <<'EOF'
chore(config): 默认 DATABASE_URL 指向 zak2 库

与独立 PG 实例对齐，导入源改用 ZAK_IMPORT_DATABASE_URL。
EOF
)"
```

---

### Task 3: Alembic 脚手架 + 拷贝 zak DDL 初始链

**Files:**
- Modify: `backend/pyproject.toml`（加 `alembic>=1.14.0` 到 dependencies）
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`（`alembic init` 生成即可）
- Create: `backend/alembic/ddl/`（从 `../zak/alembic/ddl/` 拷贝 `initial.py` `cache.py` `public_bars.py`）
- Create: `backend/alembic/versions/`（拷贝 zak 的 `001`–`006`，改 import 为相对 `ddl`）
- Create: `backend/alembic/README.md`（说明来源与升级命令）
- Run: `uv lock` 更新 `backend/uv.lock`

**Interfaces:**
- Produces: `cd backend && uv run alembic upgrade head` 可在空库创建 schema/表
- Consumes: 兄弟路径 `../zak/alembic/`（只读拷贝；若本机无 zak，从已提交到本仓的 ddl 继续）

- [ ] **Step 1: 加依赖并 init**

```bash
cd backend
# 编辑 pyproject.toml dependencies 增加: "alembic>=1.14.0",
uv lock && uv sync --extra dev
uv run alembic init alembic
```

- [ ] **Step 2: 拷贝 DDL 与 versions**

假设兄弟仓库在 `../../zak` 相对 `backend/`，即仓库根的 `../zak`：

```bash
ROOT="$(cd .. && pwd)"
mkdir -p alembic/ddl
cp "$ROOT/../zak/alembic/ddl/"*.py alembic/ddl/
cp "$ROOT/../zak/alembic/versions/"*.py alembic/versions/
# 删除 alembic init 自带的空 versions 占位若冲突
```

若 `../zak` 不存在：从本机已有 zak 检出路径拷贝；**提交时 ddl/versions 必须进 git**，避免他人无 zak 无法构建。

检查 `001_initial_schemas.py`：将

```python
from ddl.initial import ALL_STATEMENTS, DOWNGRADE_STATEMENTS
```

保持不变（`env.py` 把 `alembic/` 加入 `sys.path`）。同样检查 `004` 等对 `ddl.cache` / `ddl.public_bars` 的 import。

- [ ] **Step 3: 写 `env.py`（用 zak2 settings，不依赖 vnpy）**

```python
"""Alembic 环境：DATABASE_URL 来自 app.core.settings。"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import get_settings  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None
_SEARCH_PATH = "auth,app,chat,cache,system,public"


def _database_url() -> str:
    url = get_settings().database_url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        connection.execute(text(f"SET search_path TO {_SEARCH_PATH}"))
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

`alembic.ini`：`script_location = alembic`；`sqlalchemy.url` 可留占位（online 会覆盖）。

`alembic/README.md`：

```markdown
# zak2 Alembic

初始 DDL 自 zak `alembic/ddl` + versions `001`–`006` 拷贝并去 vnpy 依赖。
升级：`cd backend && uv run alembic upgrade head`
```

- [ ] **Step 4: 空库升级冒烟（需本机 Postgres）**

```bash
# 若无 zak2 角色/库：
# createuser zak2 -P  ; createdb -O zak2 zak2
cd backend
DATABASE_URL=postgresql+psycopg://zak2:zak2@localhost:5432/zak2 uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://zak2:zak2@localhost:5432/zak2 uv run alembic current
```

Expected: `current` 显示 `006_...`（或链顶端 revision id）

无本机 PG 时：Task 5 Compose 起来后再验；本步至少保证文件与 `uv run alembic history` 无报错。

```bash
uv run alembic history
```

Expected: 列出 001→006

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/alembic.ini backend/alembic \
  backend/alembic/README.md
git commit -m "$(cat <<'EOF'
feat(db): 引入 Alembic 并接入初始 schema 链

拷贝 zak DDL 作为起点，env 改读 zak2 settings，迁库主权收归本仓。
EOF
)"
```

---

### Task 4: `web_team_reports` 迁入 Alembic，去掉运行时 DDL

**Files:**
- Create: `backend/alembic/versions/007_web_team_reports.py`
- Modify: `backend/app/services/team_reports.py`（删除 `_DDL` / `ensure_web_team_reports_table` 调用）
- Modify: `backend/app/services/ops_sync_limit_list.py`、`ops_sync_stock_industry.py`——若仍有 `CREATE TABLE IF NOT EXISTS`，改为假设表已存在（Alembic 001/后续已建则删 DDL；若 zak DDL 已含该表则只删运行时 DDL）
- Test: `backend/tests/test_team_reports_no_runtime_ddl.py`

**Interfaces:**
- Produces: revision `007_web_team_reports`；`persist_team_report` 不再执行 DDL

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

import app.services.team_reports as tr


def test_team_reports_has_no_create_table_ddl() -> None:
    src = Path(tr.__file__).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS" not in src
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_team_reports_no_runtime_ddl.py -v`  
Expected: FAIL

- [ ] **Step 3: 写 007 迁移并删运行时 DDL**

`007_web_team_reports.py`：

```python
"""app.web_team_reports（原运行时旁路建表）。"""

from alembic import op

revision = "007_web_team_reports"
down_revision = "006_dbbardata_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.web_team_reports (
          id bigserial PRIMARY KEY,
          user_id uuid NOT NULL,
          symbol text NOT NULL,
          exchange text NOT NULL,
          vt_symbol text NOT NULL DEFAULT '',
          title text NOT NULL DEFAULT '',
          body text NOT NULL,
          summary text NOT NULL DEFAULT '',
          mode text NOT NULL DEFAULT 'fast',
          context_json text NOT NULL DEFAULT '',
          created_at text NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_web_team_reports_user_vt
        ON app.web_team_reports (user_id, vt_symbol, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.web_team_reports")
```

**注意：** `down_revision` 必须等于 `uv run alembic heads` 打印的 006 revision 字符串（可能是 `006_dbbardata_perf_indexes` 或短 hash——以文件内 `revision =` 为准）。

`team_reports.py`：删除 `_DDL`、`ensure_web_team_reports_table`；所有 `ensure_web_team_reports_table(db)` 调用删除。

对 `ops_sync_limit_list.py` / `ops_sync_stock_industry.py`：若 zak DDL 已含 `limit_list_daily` / `stock_industry`，删除文件内 `CREATE TABLE IF NOT EXISTS` 块；保留 INSERT/UPSERT 逻辑。

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/test_team_reports_no_runtime_ddl.py -q
uv run alembic history | head
```

Expected: 测试 PASS；history 含 007

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/007_web_team_reports.py backend/app/services/team_reports.py \
  backend/app/services/ops_sync_limit_list.py backend/app/services/ops_sync_stock_industry.py \
  backend/tests/test_team_reports_no_runtime_ddl.py
git commit -m "$(cat <<'EOF'
refactor(db): web_team_reports 纳入 Alembic

去掉运行时旁路建表，空库只依赖 upgrade head。
EOF
)"
```

---

### Task 5: Compose 自带 postgres + redis + 迁移入口

**Files:**
- Modify: `docker-compose.yml`
- Create: `backend/scripts/docker-entrypoint.sh`
- Modify: `backend/Dockerfile`（COPY alembic、entrypoint）
- Modify: `scripts/docker-up.sh`（注释即可）
- Modify: `scripts/dev.sh`（启动 API 前可选提示 alembic；不强制起 Docker PG）

**Interfaces:**
- Produces: `docker compose up --build` 无宿主机 zak 可起；api 启动前 `alembic upgrade head`

- [ ] **Step 1: 写 entrypoint**

`backend/scripts/docker-entrypoint.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "alembic upgrade head..."
alembic upgrade head
exec "$@"
```

`chmod +x backend/scripts/docker-entrypoint.sh`

- [ ] **Step 2: 改 Dockerfile**

在 `COPY app ./app` 同时：

```dockerfile
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`quote-collector` **不要**跑迁移（或同样无害跑 upgrade）：compose 里 collector 覆盖 `entrypoint` 为空或 `entrypoint: ["python","-m","app.quote_collector"]` 且 **不**走 upgrade——推荐：

```yaml
quote-collector:
  entrypoint: ["python", "-m", "app.quote_collector"]
```

仅 `api` 使用默认 ENTRYPOINT。

- [ ] **Step 3: 重写 `docker-compose.yml`**

```yaml
# zak2：postgres + redis + api + quote-collector + web
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: zak2
      POSTGRES_PASSWORD: zak2
      POSTGRES_DB: zak2
    ports:
      - "5432:5432"
    volumes:
      - zak2_pg:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U zak2 -d zak2"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+psycopg://zak2:zak2@postgres:5432/zak2
      REDIS_URL: redis://redis:6379/0
      CORS_ORIGINS: ${DOCKER_CORS_ORIGINS:-http://localhost:8080,http://127.0.0.1:8080}
      API_HOST: 0.0.0.0
      API_PORT: "8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://127.0.0.1:8000/health"]
      interval: 10s
      timeout: 3s
      retries: 8
      start_period: 40s

  quote-collector:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+psycopg://zak2:zak2@postgres:5432/zak2
      REDIS_URL: redis://redis:6379/0
    entrypoint: ["python", "-m", "app.quote_collector"]
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  web:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "8080:80"
    depends_on:
      api:
        condition: service_healthy

volumes:
  zak2_pg:
```

去掉 `extra_hosts` / `host.docker.internal` 默认路径。

- [ ] **Step 4: 验证 Compose**

```bash
cp -n .env.example .env
docker compose up --build -d
curl -sf http://127.0.0.1:8000/health
docker compose logs api | head -40
```

Expected: health 200；日志含 `alembic upgrade` 成功；**不需要**本机 zak 的 PG/Redis（若本机 5432/6379 已被占用，改 compose 端口映射如 `5433:5432` / `6380:6379` 并同步文档）。

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml backend/Dockerfile backend/scripts/docker-entrypoint.sh scripts/docker-up.sh scripts/dev.sh
git commit -m "$(cat <<'EOF'
feat(compose): 编入 postgres 与 redis 并启动前迁移

默认不再依赖宿主机 zak 实例，api 入口自动 alembic upgrade。
EOF
)"
```

---

### Task 6: Ops 去 CLI + 前端标签

**Files:**
- Modify: `backend/app/services/ops_scheduler.py`（`run_hint`）
- Modify: `backend/app/services/ops_catalog.py`（`collect_quotes` 描述文案）
- Modify: `backend/app/schemas/ops.py`（可选 `status_label: str`）
- Modify: `frontend/src/views/OpsView.vue`
- Modify: `frontend/src/api/ops.ts`（若加字段）
- Test: `backend/tests/test_ops_run_hints.py`

**Interfaces:**
- Produces: `list_scheduler_jobs` 中非 RUNNABLE：`collect_quotes` → hint 仅 collector；其它 → `未实现：见 docs/product-roadmap.md`；禁止字符串 `zak CLI`

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import MagicMock, patch

from app.services import ops_scheduler


def test_run_hints_have_no_zak_cli() -> None:
    db = MagicMock()
    with patch.object(ops_scheduler, "load_scheduler_config", return_value={"config": {}}), patch.object(
        ops_scheduler, "load_job_run_meta", return_value=None
    ):
        rows = {r["job_id"]: r for r in ops_scheduler.list_scheduler_jobs(db)}
    assert "zak CLI" not in (rows["enrich_market_quotes"]["run_hint"] or "")
    assert "collector" in (rows["collect_quotes"]["run_hint"] or "").lower() or "quote_collector" in (
        rows["collect_quotes"]["run_hint"] or ""
    )
    assert rows["purge_stale_cache"]["run_hint"] is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_ops_run_hints.py -v`  
Expected: FAIL（仍含 zak CLI）

- [ ] **Step 3: 改 hint 与 UI**

`ops_scheduler.py` 中 `run_hint`：

```python
"run_hint": (
    None
    if spec.job_id in RUNNABLE_JOB_IDS
    else (
        "请启动：python -m app.quote_collector（本实例内勿多开）"
        if spec.job_id == "collect_quotes"
        else "未实现：见 docs/product-roadmap.md"
    )
),
"status_label": (
    "可跑"
    if spec.job_id in RUNNABLE_JOB_IDS
    else ("独立进程" if spec.job_id == "collect_quotes" else "未实现")
),
```

`SchedulerJobOut` 增加：`status_label: str = "可跑"`

`ops_catalog.py` 中 `collect_quotes` description 改为：`zak2 quote-collector → Redis（独立进程）`

`OpsView.vue`：

```vue
<span v-else class="muted tip" :title="j.run_hint || ''">{{ j.status_label || '未实现' }}</span>
```

`ops.ts` 类型加 `status_label?: string`

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/test_ops_run_hints.py tests/test_ops_scheduler_defaults.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_scheduler.py backend/app/services/ops_catalog.py \
  backend/app/schemas/ops.py backend/tests/test_ops_run_hints.py \
  frontend/src/views/OpsView.vue frontend/src/api/ops.ts
git commit -m "$(cat <<'EOF'
fix(ops): 去掉 zak CLI 提示并区分未实现与独立进程

运维引导仅指向本仓 collector 或产品路线。
EOF
)"
```

---

### Task 7: 归档 gap + 产品路线 + README/架构/smoke

**Files:**
- Create: `docs/archive/gap-vs-desktop.md`（由原文件移动并加归档头）
- Delete: `docs/gap-vs-desktop.md`（移动后）
- Create: `docs/product-roadmap.md`
- Modify: `README.md`、`docs/architecture-p1.md`、`docs/smoke-checklist.md`
- Modify: `scripts/quote_collector.sh` 注释

- [ ] **Step 1: 归档缺口表**

```bash
mkdir -p docs/archive
git mv docs/gap-vs-desktop.md docs/archive/gap-vs-desktop.md
```

在 `docs/archive/gap-vs-desktop.md` 最上方插入：

```markdown
> **已归档（2026-08-11）。** zak2 独立演进后不再维护本对照表；排期见 [docs/product-roadmap.md](../product-roadmap.md)。以下内容仅供历史参考。

```

- [ ] **Step 2: 写 `docs/product-roadmap.md`**

```markdown
# zak2 产品路线

## 定位

独立 Web 量化终端：自有 PostgreSQL / Redis / Alembic；不依赖 zak 桌面运行时与 CLI。

## 当前基线

- 登录、自选、选股 Hub、市场/板块/雷达、笔记/Feed、回测薄、AI、Ops
- 进程：`api` + `quote-collector` + `web`
- 数据：Compose 默认自带 PG/Redis；可选 `scripts/import_from_zak.py` 一次性导入

## 近期待办

1. 完成本独立演进落地（Compose / Alembic / `zak2:` 前缀 / 去 CLI 文案 / 导入脚本）
2. Ops planned job 透明化与健康面板打磨
3. 候选（另立项）：行情 enrich 因子、AI 只读持仓/信号工具、其它 Web 体验

## 明确不做（直到本文件改口）

- 与桌面双写同步
- 依赖 zak CLI 完成运维
- 交易下单链路

设计总纲：[docs/superpowers/specs/2026-08-11-zak2-independent-evolution-design.md](./superpowers/specs/2026-08-11-zak2-independent-evolution-design.md)
```

- [ ] **Step 3: 更新 README / architecture-p1 / smoke / quote_collector.sh**

`README.md`：

- 首段改为：自有 PG/Redis；Schema 主权在本仓 Alembic  
- 前置：`uv run alembic upgrade head`（在 `backend/`），不再「zak 侧 db upgrade」  
- 能力表链接：`product-roadmap` 替代 gap  
- Docker：自带 postgres/redis  
- 删除「桌面同用户历史可见」作为验收要点；改为「导入后可登录」可选  

`architecture-p1.md` 决策表：

| 复用 | 自有 PostgreSQL / Redis；业务在本仓；不 import vnpy_* |
| Schema | zak2 Alembic |
| 目标 | 以 product-roadmap 为准，非全量对齐桌面 |

`smoke-checklist.md`：增加 Alembic、自有库、`zak2:meta:quote_count`；删除跨端桌面可见断言。

`scripts/quote_collector.sh`：注释改为「本实例内勿多开 collector」。

- [ ] **Step 4: 检查死链**

```bash
rg -n 'gap-vs-desktop' --glob '*.md' .
```

把仍指向旧路径的改成 `docs/archive/gap-vs-desktop.md` 或 roadmap。

- [ ] **Step 5: Commit**

```bash
git add docs/archive/gap-vs-desktop.md docs/product-roadmap.md README.md \
  docs/architecture-p1.md docs/smoke-checklist.md scripts/quote_collector.sh
git commit -m "$(cat <<'EOF'
docs: 归档桌面缺口表并建立 zak2 产品路线

排期与验收改以独立演进和 roadmap 为准。
EOF
)"
```

---

### Task 8: 一次性导入脚本 `import_from_zak.py`

**Files:**
- Create: `scripts/import_from_zak.py`
- Create: `backend/tests/test_import_from_zak_tables.py`（测表清单与 truncate 顺序纯逻辑）
- Modify: `README.md`（用法一小节）

**Interfaces:**
- Produces: CLI  
  `ZAK_IMPORT_DATABASE_URL=... DATABASE_URL=... python scripts/import_from_zak.py [--force] [--with-market-sync-tables]`  
- 默认表：业务态；跳过 `public.dbbardata` / `public.dbbaroverview`；`--with-market-sync-tables` 增加 universe/calendar/limit_list/sector_flow 等

- [ ] **Step 1: 写表清单单测**

`backend/app/services/zak_import.py`（逻辑放 backend 便于测；脚本薄包装）：

```python
"""从旧 zak PG 一次性导入到 zak2（truncate-then-copy）。"""

from __future__ import annotations

# 子表在前，父表在后（truncate CASCADE 时按此顺序亦可统一 CASCADE）
DEFAULT_COPY_TABLES: list[str] = [
    "auth.users",
    "auth.user_preferences",
    "app.watchlist",
    "app.watchlist_groups",
    "app.watchlist_group_members",
    "app.watchlist_positions",
    "app.screener_schemes",
    "app.screener_recipes",
    "app.screener_runs",
    "app.trading_playbook_sections",
    "app.trading_playbook_discipline_daily",
    "app.stock_note_memos",
    "app.stock_note_entries",
    "app.feed_subscriptions",
    "app.feed_items",
    "app.feed_item_reads",
    "app.trading_plans",
    "app.trading_plan_symbols",
    "app.notify_delivery_log",
    "app.backtest_runs",
    "app.web_team_reports",
    "chat.sessions",
    "chat.messages",
]

MARKET_SYNC_TABLES: list[str] = [
    "app.meta",
    "app.universe",
    "app.stock_industry",
    "app.trade_calendar",
    "app.limit_list_daily",
    "app.sector_flow_daily",
    "app.sector_flow_intraday",
    "app.emotion_limit_ladder_daily",
]


def tables_for_import(*, with_market_sync: bool) -> list[str]:
    out = list(DEFAULT_COPY_TABLES)
    if with_market_sync:
        out.extend(MARKET_SYNC_TABLES)
    return out
```

测试：

```python
from app.services.zak_import import tables_for_import


def test_default_skips_bars() -> None:
    tables = tables_for_import(with_market_sync=False)
    assert "public.dbbardata" not in tables
    assert "auth.users" in tables


def test_market_flag_adds_universe() -> None:
    assert "app.universe" in tables_for_import(with_market_sync=True)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_import_from_zak_tables.py -v`  
Expected: FAIL

- [ ] **Step 3: 实现 copy 与 CLI**

在 `zak_import.py` 增加：

```python
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _eng(url: str) -> Engine:
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True)


def target_has_rows(engine: Engine, table: str) -> bool:
    with engine.connect() as conn:
        return bool(conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1")).first())


def import_tables(
    source_url: str,
    target_url: str,
    tables: list[str],
    *,
    force: bool,
) -> dict[str, int]:
    src = _eng(source_url)
    dst = _eng(target_url)
    counts: dict[str, int] = {}
    if not force:
        for t in tables:
            if target_has_rows(dst, t):
                raise RuntimeError(f"目标表非空：{t}；请传 --force 或清空后再导")
    with dst.begin() as conn:
        for t in tables:
            conn.execute(text(f"TRUNCATE {t} CASCADE"))
    # 逐表：src 读全量 → dst executemany
    with src.connect() as sconn, dst.begin() as dconn:
        for t in tables:
            rows = sconn.execute(text(f"SELECT * FROM {t}")).mappings().all()
            if not rows:
                counts[t] = 0
                continue
            cols = list(rows[0].keys())
            col_list = ", ".join(cols)
            placeholders = ", ".join(f":{c}" for c in cols)
            dconn.execute(
                text(f"INSERT INTO {t} ({col_list}) VALUES ({placeholders})"),
                [dict(r) for r in rows],
            )
            counts[t] = len(rows)
    return counts
```

`scripts/import_from_zak.py`：

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.zak_import import import_tables, tables_for_import  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="从 zak PG 一次性导入到 zak2")
    p.add_argument("--force", action="store_true")
    p.add_argument("--with-market-sync-tables", action="store_true")
    args = p.parse_args()
    src = os.environ.get("ZAK_IMPORT_DATABASE_URL") or ""
    dst = os.environ.get("DATABASE_URL") or ""
    if not src or not dst:
        print("需要 ZAK_IMPORT_DATABASE_URL 与 DATABASE_URL", file=sys.stderr)
        return 2
    tables = tables_for_import(with_market_sync=args.with_market_sync_tables)
    counts = import_tables(src, dst, tables, force=args.force)
    for t, n in counts.items():
        print(f"{t}: {n}")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

README 增补：

```bash
# 目标库已 alembic upgrade 后：
ZAK_IMPORT_DATABASE_URL=postgresql+psycopg://zak:zak@localhost:5432/zak \
DATABASE_URL=postgresql+psycopg://zak2:zak2@localhost:5432/zak2 \
python scripts/import_from_zak.py --force
```

- [ ] **Step 4: 跑单测**

```bash
cd backend && uv run pytest tests/test_import_from_zak_tables.py -q
```

Expected: PASS  

（双库集成导入为手工验收，不强制 CI。）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/zak_import.py backend/tests/test_import_from_zak_tables.py \
  scripts/import_from_zak.py README.md
git commit -m "$(cat <<'EOF'
feat(db): 增加从 zak 一次性导入脚本

truncate 后拷贝业务表，默认跳过日 K 大表，导入后两库分叉。
EOF
)"
```

---

### Task 9: 总验收

**Files:** 无新代码（或修漏网）

- [ ] **Step 1: 自动化**

```bash
./scripts/check.sh
cd backend && rg -n 'zak CLI|host\.docker\.internal:5432/zak|KEY_PREFIX = "zak"' app tests ../scripts ../docker-compose.yml ../README.md ../.env.example || true
```

Expected: pytest+build 绿；扫到的命中应为 0 或仅 archive 文档。

- [ ] **Step 2: Compose 手工**

```bash
docker compose down -v
docker compose up --build -d
curl -sf http://127.0.0.1:8000/health
# 可选：创建用户后登录；或跑 import 脚本
```

Expected: 不依赖宿主机 zak 库即可 health 绿。

- [ ] **Step 3: Redis 前缀手工（有 TickFlow 时）**

```bash
docker compose exec redis redis-cli GET zak2:meta:quote_count
docker compose exec redis redis-cli GET zak:meta:quote_count
```

Expected: 前者在采集后有值；后者为空或不存在。

- [ ] **Step 4: 若有漏网则修并追加 commit**（按中文规范）

- [ ] **Step 5: 完成**

无需空 commit。在 PR/对话中勾选 spec 验收项。

---

## Spec coverage（自检）

| Spec 要求 | Task |
|-----------|------|
| Compose 自带 PG/Redis | 5 |
| 默认 DATABASE_URL=zak2 | 2 |
| Alembic + 启动 upgrade | 3、4、5 |
| 去掉运行时 CREATE TABLE | 4 |
| Redis `zak2:*` | 1 |
| 去 CLI / planned | 6 |
| 归档 gap + roadmap | 7 |
| import_from_zak | 8 |
| 验收 | 9 |
| 不实现 enrich 全量 job | 遵守非目标 |

## 执行交接

Plan 已保存到 `docs/superpowers/plans/2026-08-11-zak2-independent-evolution.md`。
