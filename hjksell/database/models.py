"""SQLAlchemy models for the local HJKsell data store."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all HJKsell tables."""


class ItemStatus(StrEnum):
    IN_STOCK = "IN_STOCK"
    SOLD = "SOLD"


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False, index=True)
    photo_path: Mapped[Optional[str]] = mapped_column(String(1024))
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_price_pln: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    cost_byn: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ItemStatus.IN_STOCK.value)
    sale_price_byn: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    sale_date: Mapped[Optional[date]] = mapped_column(Date)
    telegram_channel_id: Mapped[Optional[str]] = mapped_column(String(128))
    telegram_message_id: Mapped[Optional[int]] = mapped_column(Integer)
    telegram_update_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class MonthlyExpense(Base):
    __tablename__ = "monthly_expenses"
    __table_args__ = (UniqueConstraint("portfolio_id", "year", "month", name="uq_monthly_expense_portfolio_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_byn: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(String(2048))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False
    )


class ExchangeRateHistory(Base):
    __tablename__ = "exchange_rate_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class TelegramChannel(Base):
    __tablename__ = "telegram_channels"
    __table_args__ = (UniqueConstraint("portfolio_id", "channel_id", name="uq_telegram_channel_portfolio"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("portfolios.id"))
    channel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class TelegramConfig(Base):
    __tablename__ = "telegram_configs"

    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), primary_key=True)
    token: Mapped[Optional[str]] = mapped_column(String(2048))
    update_offset: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False
    )


class TelegramImport(Base):
    __tablename__ = "telegram_imports"
    __table_args__ = (
        Index("uq_telegram_import_portfolio_channel_message", "portfolio_id", "channel_id", "message_id", unique=True),
        Index("uq_telegram_import_portfolio_update", "portfolio_id", "update_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("portfolios.id"))
    channel_id: Mapped[Optional[str]] = mapped_column(String(128))
    message_id: Mapped[Optional[int]] = mapped_column(Integer)
    update_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="imported")
    error_message: Mapped[Optional[str]] = mapped_column(String(512))
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
