from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DbBarData(Base):
    """VeighNa public.dbbardata（K 线，全局共享）。"""

    __tablename__ = "dbbardata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String, nullable=False, index=True)
    datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interval: Mapped[str] = mapped_column(String, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float)
    turnover: Mapped[float | None] = mapped_column(Float)
    open_interest: Mapped[float | None] = mapped_column(Float)
    open_price: Mapped[float | None] = mapped_column(Float)
    high_price: Mapped[float | None] = mapped_column(Float)
    low_price: Mapped[float | None] = mapped_column(Float)
    close_price: Mapped[float | None] = mapped_column(Float)
