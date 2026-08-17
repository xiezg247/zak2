from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.repositories.pagination import Page, paginate


class _Base(DeclarativeBase):
    pass


class _Item(_Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)


@pytest.fixture()
def db() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    _Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([_Item(id=i, name=f"n{i}") for i in range(25)])
        session.commit()
        yield session


def test_page_pages_rounding() -> None:
    assert Page(items=[], total=0, page=1, page_size=20).pages == 0
    assert Page(items=[], total=1, page=1, page_size=20).pages == 1
    assert Page(items=[], total=20, page=1, page_size=20).pages == 1
    assert Page(items=[], total=21, page=1, page_size=20).pages == 2


def test_page_has_next_and_prev() -> None:
    first = Page(items=[], total=21, page=1, page_size=20)
    assert first.has_next is True
    assert first.has_prev is False

    last = Page(items=[], total=21, page=2, page_size=20)
    assert last.has_next is False
    assert last.has_prev is True

    single = Page(items=[], total=0, page=1, page_size=20)
    assert single.has_next is False
    assert single.has_prev is False


def test_paginate_offsets_and_wraps(db: Session) -> None:
    stmt = select(_Item).order_by(_Item.id)
    result = paginate(db, stmt, page=2, page_size=10)
    assert result.total == 25
    assert result.page == 2
    assert result.page_size == 10
    assert result.pages == 3
    assert [i.id for i in result.items] == list(range(10, 20))


def test_paginate_clamps_invalid_page(db: Session) -> None:
    stmt = select(_Item).order_by(_Item.id)
    result = paginate(db, stmt, page=0, page_size=0)
    assert result.page == 1
    assert result.page_size == 1
    assert result.total == 25
    assert len(result.items) == 1
