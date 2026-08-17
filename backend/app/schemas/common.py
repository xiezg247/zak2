"""通用响应模型：分页 + 统一包裹。"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应包裹：成功时 code=0、data 为业务数据；错误仍走 HTTP 状态码 + detail。"""

    code: int = 0
    message: str = "ok"
    data: T | None = None


class PageOut(BaseModel, Generic[T]):
    """分页列表数据：items + 总数 + 分页元信息（作为 ApiResponse 的 data）。"""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def from_page(cls, page: Any) -> "PageOut[T]":
        """从 repositories.pagination.Page 结果对象构造（duck-typing，避免 schema→repo 依赖）。"""
        return cls(
            items=page.items,
            total=page.total,
            page=page.page,
            page_size=page.page_size,
            pages=page.pages,
        )


class OkOut(BaseModel):
    """通用成功回执：写/删操作成功时返回。"""

    ok: bool = True
