from __future__ import annotations

from sqlalchemy import Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SectorFlowDaily(Base):
    __tablename__ = "sector_flow_daily"

    trade_date: Mapped[str] = mapped_column(Text, primary_key=True)
    sector_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    sector_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    net_flow_yi: Mapped[float] = mapped_column(Float, nullable=False)
    flow_source: Mapped[str] = mapped_column(Text, nullable=False, default="")


class SectorFlowIntraday(Base):
    __tablename__ = "sector_flow_intraday"

    trade_date: Mapped[str] = mapped_column(Text, primary_key=True)
    sector_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    sector_id: Mapped[str] = mapped_column(Text, primary_key=True)
    bucket_time: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    clock_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    net_flow_yi: Mapped[float] = mapped_column(Float, nullable=False)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)


class EmotionLimitLadderDaily(Base):
    __tablename__ = "emotion_limit_ladder_daily"

    trade_date: Mapped[str] = mapped_column(Text, primary_key=True)
    max_limit_times: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_board_vt_symbol: Mapped[str] = mapped_column(Text, nullable=False, default="")
    linked_board_vt_symbols: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class LimitListDaily(Base):
    """涨停列表日表（Tushare limit_list_d）；vt_symbol 为 TickFlow 风格如 SHSE.600519。"""

    __tablename__ = "limit_list_daily"

    trade_date: Mapped[str] = mapped_column(Text, primary_key=True)
    vt_symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    ts_code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    limit_times: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    first_time: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_time: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fd_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    open_times: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    strth: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default="")


class RadarCardSnapshot(Base):
    __tablename__ = "radar_card_snapshot"
    __table_args__ = {"schema": "cache"}

    card_id: Mapped[str] = mapped_column(Text, primary_key=True)
    variant_key: Mapped[str] = mapped_column(Text, primary_key=True, default="")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[str] = mapped_column(Text, nullable=False)
