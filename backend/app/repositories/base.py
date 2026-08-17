"""数据访问层抽象基类：单主键 + user_id 的 ORM 通用 CRUD 与分页。

子类声明 ``model`` 与可选 ``order_by``，即获得 list_all/get/exists/count/
paginate/create/update/delete 骨架；复合主键或特殊写逻辑请在子类覆写。

非 ORM 的仓库（positions、signal_panel）不继承本基类，独立实现实例方法，
但保持相同的 ``Repo(db, user_id)`` 构造约定。
"""

from __future__ import annotations

from abc import ABC
from typing import Any, ClassVar, Generic, TypeVar, cast
from uuid import uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.base import Base
from app.repositories.pagination import Page, count_rows, paginate

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(ABC, Generic[ModelT]):
    """单主键 + user_id 的 ORM 仓库基类。

    子类必需：
        model: ORM 模型类
    子类可选：
        id_attr: 主键列名，默认 "id"
        order_by: 默认排序（tuple，可单个元素）
        _new_id: 主键生成策略，默认 str(uuid4())
    """

    model: ClassVar[type[Base]]
    id_attr: ClassVar[str] = "id"
    order_by: ClassVar[tuple[Any, ...]] = ()

    def __init__(self, db: Session, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    # ---- 查询 ----

    def _select(self) -> Select:
        return select(self.model).where(cast(Any, self.model).user_id == self.user_id)

    def list_all(self, *, limit: int | None = None) -> list[ModelT]:
        stmt = self._select()
        if self.order_by:
            stmt = stmt.order_by(*self.order_by)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt))

    def get(self, key: Any) -> ModelT | None:
        return cast(
            ModelT | None,
            self.db.scalar(
                select(self.model).where(
                    cast(Any, self.model).user_id == self.user_id,
                    getattr(self.model, self.id_attr) == key,
                )
            ),
        )

    def exists(self, key: Any) -> bool:
        return self.get(key) is not None

    def count(self) -> int:
        return count_rows(self.db, self._select())

    def paginate(self, *, page: int = 1, page_size: int = 20) -> Page[ModelT]:
        stmt = self._select()
        if self.order_by:
            stmt = stmt.order_by(*self.order_by)
        return paginate(self.db, stmt, page=page, page_size=page_size)

    # ---- 写 ----

    def _new_id(self) -> str:
        return str(uuid4())

    def _id_is_autoincrement(self) -> bool:
        col = self.model.__table__.columns[self.id_attr]
        return bool(getattr(col, "autoincrement", False))

    def create(self, **values: Any) -> ModelT:
        values.setdefault("user_id", self.user_id)
        if self.id_attr not in values and not self._id_is_autoincrement():
            values[self.id_attr] = self._new_id()
        row = cast(ModelT, self.model(**values))
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(self, key: Any, **values: Any) -> ModelT | None:
        row = self.get(key)
        if row is None:
            return None
        for field, value in values.items():
            setattr(row, field, value)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, key: Any) -> bool:
        row = self.get(key)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
