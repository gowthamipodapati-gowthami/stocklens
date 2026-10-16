"""FastAPI HTTP layer. No SQL or calculation code in the UI."""
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
import re
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from . import models, repositories as repo
from .services import analytics, forecast, market_data

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / 'frontend'
SYMBOL_PATTERN = re.compile(r'^[A-Z0-9^][A-Z0-9.\-^=]{0,19}$')

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title='StockLens API', version='1.0.0',
              description='Separate data, analytics, forecast and frontend layers.', lifespan=lifespan)


def normalized_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise HTTPException(status_code=422, detail='Invalid symbol. Example: AAPL, TCS.NS, BTC-USD.')
    return symbol

@app.get('/api/health')
def health():
    return {'status':'ok', 'app':'StockLens', 'database':'sqlite' if 'sqlite:' in str(engine.url) else 'postgresql'}

@app.get('/api/symbols')
def symbols():
    return {'symbols':market_data.PRESETS}

@app.get('/api/stocks/{symbol}/dashboard')
def dashboard(symbol: str, period: str = Query('5y'), refresh: bool = Query(False),
              db: Session = Depends(get_db)):
    symbol = normalized_symbol(symbol)
    if period not in analytics.VALID_PERIODS:
        raise HTTPException(status_code=422, detail='Choose 1y, 3y, 5y, 10y or all.')
    try:
        stock, prices = market_data.ensure_stock(db, symbol, force=refresh)
    except market_data.MarketDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = analytics.calculate_dashboard(prices, period)
    result.update({'symbol':stock.symbol, 'name':stock.name, 'currency':stock.currency,
                   'source':stock.source, 'period':period,
                   'data_updated_at':stock.last_refreshed_at.isoformat() if stock.last_refreshed_at else None})
    return result

@app.get('/api/stocks/{symbol}/forecast')
def predict(symbol: str, days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db)):
    symbol = normalized_symbol(symbol)
    try:
        stock, prices = market_data.ensure_stock(db, symbol)
    except market_data.MarketDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    as_of = prices[-1].trading_date
    run = repo.recent_forecast(db, stock.id, as_of, days)
    if run is None:
        try:
            computation = forecast.calculate_forecast(prices, days)
        except forecast.ForecastUnavailable as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        run = repo.save_forecast(db, stock.id, as_of, days, computation)
        run = repo.recent_forecast(db, stock.id, as_of, days)
    data = [{'date':point.trading_date.isoformat(), 'predicted':round(point.predicted_close,4),
             'lower':round(point.lower_bound,4), 'upper':round(point.upper_bound,4)} for point in run.points]
    return {'symbol':symbol, 'source':stock.source, 'as_of_date':as_of.isoformat(),
            'days':days, 'model_name':run.model_name, 'mae':round(run.mae,4),
            'baseline_mae':round(run.baseline_mae,4), 'rmse':round(run.rmse,4),
            'validation_points':run.validation_points, 'base_close':round(prices[-1].close,4),
            'points':data, 'cached_at':(run.created_at if run.created_at.tzinfo else run.created_at.replace(tzinfo=timezone.utc)).isoformat(),
            'note':'Exploratory model; confidence band is heuristic, not calibrated or a guarantee. Not financial advice.'}

app.mount('/assets', StaticFiles(directory=str(FRONTEND)), name='frontend_assets')

@app.get('/')
def index():
    return FileResponse(FRONTEND / 'index.html')

@app.get('/{path:path}', include_in_schema=False)
def spa_fallback(path: str):
    # Do not return HTML for invalid API paths.
    if path.startswith('api/') or path.startswith('assets/'):
        raise HTTPException(status_code=404, detail='Not found')
    return FileResponse(FRONTEND / 'index.html')
