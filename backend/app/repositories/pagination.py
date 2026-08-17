"""统一分页工具：Page 结果对象 + count/paginate 辅助函数。"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")
U = TypeVar("U")


@dataclass
class Page(Generic[T]):
    """分页结果：items + 总数 + 页码信息。"""

    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        if self.total <= 0:
            return 0
        return math.ceil(self.total / self.page_size)

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def map(self, fn: Callable[[T], U]) -> Page[U]:
        """把 items 逐项映射为新类型，保留分页元信息。"""
        return Page(
            items=[fn(x) for x in self.items],
            total=self.total,
            page=self.page,
            page_size=self.page_size,
        )


def count_rows(db: Session, stmt: Select) -> int:
    """统计查询语句的总行数（忽略 order_by/limit/offset）。"""
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    return int(db.scalar(count_stmt) or 0)


def paginate(db: Session, stmt: Select, *, page: int, page_size: int) -> Page:
    """对查询语句分页，返回 Page。stmt 不应自行携带 limit/offset。"""
    page = max(1, int(page))
    page_size = max(1, int(page_size))
    total = count_rows(db, stmt)
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return Page(items=rows, total=total, page=page, page_size=page_size)
