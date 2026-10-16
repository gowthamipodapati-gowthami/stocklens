"""All database reads and writes are centralized here."""
from datetime import datetime, timedelta, timezone
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from .models import Stock, DailyPrice, ForecastRun, ForecastPoint


def get_stock(db: Session, symbol: str) -> Stock | None:
    return db.scalar(select(Stock).where(Stock.symbol == symbol))


def list_prices(db: Session, stock_id: int) -> list[DailyPrice]:
    return list(db.scalars(select(DailyPrice).where(DailyPrice.stock_id == stock_id).order_by(DailyPrice.trading_date)))


def save_prices(db: Session, symbol: str, name: str, currency: str, source: str, rows: Sequence[dict]) -> Stock:
    stock = get_stock(db, symbol)
    if stock is None:
        stock = Stock(symbol=symbol, name=name, currency=currency, source=source)
        db.add(stock)
        db.flush()
    stock.name = name
    stock.currency = currency
    stock.source = source
    existing = {x.trading_date: x for x in list_prices(db, stock.id)}
    for row in rows:
        day = row['trading_date']
        record = existing.get(day)
        if record is None:
            record = DailyPrice(stock_id=stock.id, trading_date=day)
            db.add(record)
        for field in ('open', 'high', 'low', 'close', 'volume'):
            setattr(record, field, row[field])
    stock.last_refreshed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(stock)
    return stock


def recent_forecast(db: Session, stock_id: int, as_of_date, days: int) -> ForecastRun | None:
    threshold = datetime.now(timezone.utc) - timedelta(hours=12)
    candidate = db.scalar(
        select(ForecastRun)
        .options(selectinload(ForecastRun.points))
        .where(ForecastRun.stock_id == stock_id, ForecastRun.as_of_date == as_of_date,
               ForecastRun.horizon_days == days, ForecastRun.created_at >= threshold)
        .order_by(ForecastRun.created_at.desc()).limit(1)
    )
    return candidate


def save_forecast(db: Session, stock_id: int, as_of_date, days: int, results: dict) -> ForecastRun:
    run = ForecastRun(stock_id=stock_id, as_of_date=as_of_date, horizon_days=days,
                      model_name=results['model_name'], mae=results['mae'],
                      baseline_mae=results['baseline_mae'], rmse=results['rmse'],
                      validation_points=results['validation_points'])
    db.add(run)
    db.flush()
    for i, item in enumerate(results['points'], start=1):
        db.add(ForecastPoint(run_id=run.id, step=i, trading_date=item['date'],
                             predicted_close=item['predicted'], lower_bound=item['lower'],
                             upper_bound=item['upper']))
    db.commit()
    return run
