"""绿场创建 public.dbbardata / dbbaroverview（VeighNa 日 K）。"""

# env.py 已将 alembic/ 加入 sys.path
from ddl.public_bars import (
    PUBLIC_BAR_ANALYZE,
    PUBLIC_BAR_INDEX_DOWN,
    PUBLIC_BAR_INDEX_UP,
    PUBLIC_BAR_TABLE_DOWN,
    PUBLIC_BAR_TABLE_UP,
)

from alembic import op

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
