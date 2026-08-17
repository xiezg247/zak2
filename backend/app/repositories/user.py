"""用户数据访问：User 主体查询。

User 表没有 ``user_id`` 作用域列（其自身即主体），故不继承
``BaseRepository``，独立实现 ``UserRepository(db)`` 构造约定。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """用户主体查询（按 id / username）。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id))

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))
