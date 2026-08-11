# 绿场 public 日 K 表建表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alembic `009` 在绿场创建 `public.dbbardata` / `dbbaroverview`（含唯一索引与性能索引），文档说明手动 Ops 补数。

**Architecture:** 在 `alembic/ddl/public_bars.py` 增加建表 SQL 常量；`009_create_public_bars.py` 执行建表 + 唯一索引 + `PUBLIC_BAR_INDEX_UP`；本刀不调用 fill job。

**Tech Stack:** Alembic、PostgreSQL、pytest（测 DDL 常量）

**Spec:** `docs/superpowers/specs/2026-08-11-public-bars-schema-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*；不改 `bar_download` / `ops_bars_fill` 业务逻辑
- **不**自动拉日 K；不从 zak 拷行数据
- 幂等：`CREATE TABLE IF NOT EXISTS`、索引 `IF NOT EXISTS`
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/alembic/ddl/public_bars.py` | 建表 + 唯一索引 SQL 常量 |
| `backend/alembic/versions/009_create_public_bars.py` | upgrade / downgrade |
| `backend/tests/test_public_bars_ddl.py` | 断言常量含表名与唯一索引名 |
| `docs/smoke-checklist.md` | upgrade 后手动补全自选日 K |
| `docs/product-roadmap.md` | 记日 K 绿场建表 |

---

### Task 1: DDL 常量 + Alembic 009

**Files:**
- Modify: `backend/alembic/ddl/public_bars.py`
- Create: `backend/alembic/versions/009_create_public_bars.py`
- Create: `backend/tests/test_public_bars_ddl.py`

**Interfaces:**
- Produces: `PUBLIC_BAR_TABLE_UP: tuple[str, ...]`（建表 + 唯一索引）；`009` revision `down_revision = "008_stock_industry_limit_list"`
- Consumes: 现有 `PUBLIC_BAR_INDEX_UP` / `PUBLIC_BAR_INDEX_DOWN`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_public_bars_ddl.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alembic"))
from ddl import public_bars as pb


def test_public_bar_table_ddl_contains_core_objects() -> None:
    blob = "\n".join(pb.PUBLIC_BAR_TABLE_UP)
    assert "CREATE TABLE IF NOT EXISTS public.dbbardata" in blob
    assert "CREATE TABLE IF NOT EXISTS public.dbbaroverview" in blob
    assert "dbbardata_symbol_exchange_interval_datetime" in blob
    assert "dbbaroverview_symbol_exchange_interval" in blob
    assert "open_price" in blob and "close_price" in blob


def test_public_bar_index_ddl_unchanged_names() -> None:
    blob = "\n".join(pb.PUBLIC_BAR_INDEX_UP)
    assert "ix_dbbardata_daily_symbol_exchange_dt" in blob
    assert "ix_dbbardata_daily_interval_sym_ex_dt" in blob
    assert "ix_dbbardata_daily_dt_brin" in blob
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_public_bars_ddl.py -v`  
Expected: FAIL（`PUBLIC_BAR_TABLE_UP` 不存在）

- [ ] **Step 3: 实现 DDL 常量**

在 `public_bars.py` 增加（置于 `PUBLIC_BAR_INDEX_UP` 之前或之后均可，保持可读）：

```python
PUBLIC_BAR_TABLE_UP: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS public.dbbardata (
      id SERIAL PRIMARY KEY,
      symbol VARCHAR NOT NULL,
      exchange VARCHAR NOT NULL,
      datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
      interval VARCHAR NOT NULL,
      volume REAL NOT NULL,
      turnover REAL NOT NULL,
      open_interest REAL NOT NULL,
      open_price REAL NOT NULL,
      high_price REAL NOT NULL,
      low_price REAL NOT NULL,
      close_price REAL NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS dbbardata_symbol_exchange_interval_datetime
    ON public.dbbardata (symbol, exchange, interval, datetime)
    """,
    """
    CREATE TABLE IF NOT EXISTS public.dbbaroverview (
      id SERIAL PRIMARY KEY,
      symbol VARCHAR NOT NULL,
      exchange VARCHAR NOT NULL,
      interval VARCHAR NOT NULL,
      count INTEGER NOT NULL,
      start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
      "end" TIMESTAMP WITHOUT TIME ZONE NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS dbbaroverview_symbol_exchange_interval
    ON public.dbbaroverview (symbol, exchange, interval)
    """,
)

PUBLIC_BAR_TABLE_DOWN: tuple[str, ...] = (
    "DROP TABLE IF EXISTS public.dbbardata CASCADE",
    "DROP TABLE IF EXISTS public.dbbaroverview CASCADE",
)
```

（若先 DROP overview 再 data 亦可；CASCADE 会清依赖索引。）

创建 `backend/alembic/versions/009_create_public_bars.py`：

```python
"""绿场创建 public.dbbardata / dbbaroverview（VeighNa 日 K）。"""

from alembic import op

# env.py 已将 alembic/ 加入 sys.path
from ddl.public_bars import (
    PUBLIC_BAR_ANALYZE,
    PUBLIC_BAR_INDEX_DOWN,
    PUBLIC_BAR_INDEX_UP,
    PUBLIC_BAR_TABLE_DOWN,
    PUBLIC_BAR_TABLE_UP,
)

revision = "009_create_public_bars"
down_revision = "008_stock_industry_limit_list"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for stmt in PUBLIC_BAR_TABLE_UP:
        op.execute(stmt)
    for stmt in PUBLIC_BAR_INDEX_UP:
        op.execute(stmt)
    for stmt in PUBLIC_BAR_ANALYZE:
        op.execute(stmt)


def downgrade() -> None:
    # 有数据环境慎用：会删除全部日 K
    for stmt in PUBLIC_BAR_INDEX_DOWN:
        op.execute(stmt)
    for stmt in PUBLIC_BAR_TABLE_DOWN:
        op.execute(stmt)
```

测试里 import 用：`from alembic.ddl import public_bars as pb` 可能失败；pytest 以 `backend` 为根时用：

```python
from ddl.public_bars import PUBLIC_BAR_TABLE_UP, PUBLIC_BAR_INDEX_UP
```

或把 `tests` 里改为 `sys.path` 指向 `alembic/`。**推荐测试写法：**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alembic"))
from ddl import public_bars as pb
```

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/test_public_bars_ddl.py -q
```

Expected: PASS

- [ ] **Step 5: 对本地 zak2 执行 upgrade（验证，非自动拉数）**

```bash
cd backend && set -a && source ../.env && set +a && uv run alembic upgrade head && uv run alembic current
```

再用 SQL 确认（可用 python/sqlalchemy）：

```sql
SELECT to_regclass('public.dbbardata'), to_regclass('public.dbbaroverview');
```

Expected: 非 NULL；`alembic_version` = `009_create_public_bars`

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/ddl/public_bars.py \
  backend/alembic/versions/009_create_public_bars.py \
  backend/tests/test_public_bars_ddl.py
git commit -m "$(cat <<'EOF'
feat(db): Alembic 009 绿场创建 public 日 K 表

补齐 dbbardata/dbbaroverview 与唯一索引、性能索引，供 Ops 补数。
EOF
)"
```

---

### Task 2: 文档

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: 更新 smoke**

在环境/库相关条目附近增加或改写：

- alembic 最新含 `009_create_public_bars`；`public.dbbardata` / `dbbaroverview` 存在  
- Ops 手动跑 **补全自选日 K**（`fill_watchlist_bars`，需 `TUSHARE_TOKEN` + 自选；本刀不自动执行）

- [ ] **Step 2: 更新 roadmap**

在近期待办或基线中注明：~~日 K 绿场建表~~（已完成 → 链本 spec）；拉数仍靠 Ops 手动。

- [ ] **Step 3: check**

```bash
./scripts/check.sh
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs: 日 K 绿场建表后补充 smoke 与路线图

说明 upgrade 后于 Ops 手动补全自选日 K。
EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| 建表 + 唯一索引 | 1 |
| 性能索引 | 1 |
| 不自动拉数 | 遵守 |
| smoke / roadmap | 2 |

## 执行交接

Plan 已保存到 `docs/superpowers/plans/2026-08-11-public-bars-schema.md`。
