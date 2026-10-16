"""Persist market history and forecast runs in SQLite or PostgreSQL (Supabase)."""
from datetime import date, datetime, timezone
from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Stock(Base):
    __tablename__ = 'stocks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default='USD', nullable=False)
    source: Mapped[str] = mapped_column(String(32), default='yahoo_finance', nullable=False)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prices: Mapped[list['DailyPrice']] = relationship(cascade='all, delete-orphan', back_populates='stock')

class DailyPrice(Base):
    __tablename__ = 'daily_prices'
    __table_args__ = (UniqueConstraint('stock_id', 'trading_date', name='uq_price_stock_day'),
                      Index('ix_daily_prices_stock_date', 'stock_id', 'trading_date'))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    stock: Mapped['Stock'] = relationship(back_populates='prices')

class ForecastRun(Base):
    __tablename__ = 'forecast_runs'
    __table_args__ = (Index('ix_forecast_run_stock_asof', 'stock_id', 'as_of_date'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    mae: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_mae: Mapped[float] = mapped_column(Float, nullable=False)
    rmse: Mapped[float] = mapped_column(Float, nullable=False)
    validation_points: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[list['ForecastPoint']] = relationship(cascade='all, delete-orphan', back_populates='run', order_by='ForecastPoint.step')

class ForecastPoint(Base):
    __tablename__ = 'forecast_points'
    __table_args__ = (UniqueConstraint('run_id', 'step', name='uq_forecast_run_step'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('forecast_runs.id', ondelete='CASCADE'), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_close: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound: Mapped[float] = mapped_column(Float, nullable=False)
    upper_bound: Mapped[float] = mapped_column(Float, nullable=False)
    run: Mapped['ForecastRun'] = relationship(back_populates='points')
