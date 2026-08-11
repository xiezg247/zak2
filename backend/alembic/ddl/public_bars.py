"""VeighNa public schema K 线表性能索引（与 vnpy_postgresql 表结构对齐）。"""

from __future__ import annotations

# interval 日 K 值为 Interval.DAILY.value → 'd'
DAILY_INTERVAL = "d"

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

PUBLIC_BAR_INDEX_UP: tuple[str, ...] = (
    # 单标的 tail：WHERE interval='d' AND symbol=? AND exchange=? AND datetime BETWEEN ...
    """
    CREATE INDEX IF NOT EXISTS ix_dbbardata_daily_symbol_exchange_dt
    ON public.dbbardata (symbol, exchange, datetime DESC)
    WHERE interval = 'd'
    """,
    # 批量 IN (symbol, exchange)：WHERE interval='d' AND (symbol, exchange) IN (...)
    """
    CREATE INDEX IF NOT EXISTS ix_dbbardata_daily_interval_sym_ex_dt
    ON public.dbbardata (interval, symbol, exchange, datetime DESC)
    WHERE interval = 'd'
    """,
    # 大表按时间维护 / 范围扫描（可选，与 symbol 索引互补）
    """
    CREATE INDEX IF NOT EXISTS ix_dbbardata_daily_dt_brin
    ON public.dbbardata USING brin (datetime)
    WHERE interval = 'd'
    """,
)

PUBLIC_BAR_INDEX_DOWN: tuple[str, ...] = (
    "DROP INDEX IF EXISTS public.ix_dbbardata_daily_dt_brin",
    "DROP INDEX IF EXISTS public.ix_dbbardata_daily_interval_sym_ex_dt",
    "DROP INDEX IF EXISTS public.ix_dbbardata_daily_symbol_exchange_dt",
)

PUBLIC_BAR_ANALYZE: tuple[str, ...] = (
    "ANALYZE public.dbbardata",
    "ANALYZE public.dbbaroverview",
)
