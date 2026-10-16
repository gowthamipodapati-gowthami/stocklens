"""Historical daily price acquisition. DEMO is clearly marked synthetic/offline."""
from datetime import datetime, date, timedelta, timezone
import math
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from .. import repositories as repo

PRESETS = [
    {'symbol':'DEMO','name':'Demo Market (Synthetic)','region':'Demo'},
    {'symbol':'AAPL','name':'Apple Inc.','region':'US'},
    {'symbol':'MSFT','name':'Microsoft','region':'US'},
    {'symbol':'NVDA','name':'NVIDIA','region':'US'},
    {'symbol':'GOOGL','name':'Alphabet','region':'US'},
    {'symbol':'AMZN','name':'Amazon','region':'US'},
    {'symbol':'TSLA','name':'Tesla','region':'US'},
    {'symbol':'RELIANCE.NS','name':'Reliance Industries','region':'India'},
    {'symbol':'TCS.NS','name':'Tata Consultancy Services','region':'India'},
    {'symbol':'INFY.NS','name':'Infosys','region':'India'},
    {'symbol':'HDFCBANK.NS','name':'HDFC Bank','region':'India'},
]

class MarketDataError(Exception):
    pass


def demo_rows() -> list[dict]:
    # fixed seed, deterministic path, deliberately NOT claimed to be market data
    rng = np.random.default_rng(2039)
    dates = pd.bdate_range(end=date.today(), periods=8 * 252)
    returns = rng.normal(0.00048, 0.014, size=len(dates))
    for index in range(len(returns)):
        if 480 < index < 530:
            returns[index] -= 0.0045
        if 1400 < index < 1470:
            returns[index] += 0.0025
    closes = 80 * np.exp(np.cumsum(returns))
    rows = []
    previous = 80.0
    for ix, dt in enumerate(dates):
        c = float(closes[ix])
        op = previous * (1 + float(rng.normal(0, 0.003)))
        high = max(op, c) * (1 + abs(float(rng.normal(0, 0.004))))
        low = min(op, c) * (1 - abs(float(rng.normal(0, 0.004))))
        rows.append(dict(trading_date=dt.date(), open=round(op, 4), high=round(high, 4),
                         low=round(low, 4), close=round(c, 4),
                         volume=int(rng.integers(2_000_000, 12_000_000))))
        previous = c
    return rows


def _fetch_yahoo(symbol: str) -> tuple[str, str, list[dict]]:
    """Fetch Yahoo's unofficial chart JSON from the backend only.

    'adjclose' is used as an adjustment factor on OHLC, keeping displayed
    closes and multi-year returns on the same dividend/split-adjusted basis.
    """
    import requests
    from datetime import datetime
    from urllib.parse import quote
    from zoneinfo import ZoneInfo
    endpoint = f'/v8/finance/chart/{quote(symbol, safe="")}'
    payload = None
    failure = ''
    for host in ('https://query1.finance.yahoo.com', 'https://query2.finance.yahoo.com'):
        try:
            response = requests.get(host + endpoint,
                                    params={'range':'10y','interval':'1d','includeAdjustedClose':'true'},
                                    headers={'User-Agent':'Mozilla/5.0 (compatible; StockLens/1.0; historical-research)',
                                             'Accept':'application/json'}, timeout=20)
            response.raise_for_status()
            payload = response.json()
            break
        except (requests.RequestException, ValueError) as exc:
            failure = type(exc).__name__
    if payload is None:
        raise MarketDataError(f'Yahoo historical data is temporarily unavailable for {symbol} ({failure}). Try DEMO or cached data.')
    try:
        chart = payload['chart']
        if chart.get('error') or not chart.get('result'):
            raise MarketDataError(f'No historical data for {symbol}. Check its Yahoo Finance ticker.')
        record = chart['result'][0]
        meta = record.get('meta') or {}
        preset = next((p for p in PRESETS if p['symbol']==symbol), {})
        name = str(meta.get('longName') or meta.get('shortName') or preset.get('name') or symbol)[:160]
        currency = str(meta.get('currency') or ('INR' if symbol.endswith(('.NS','.BO')) else 'USD'))[:8]
        tzname = meta.get('exchangeTimezoneName', 'UTC')
        try:
            tz = ZoneInfo(tzname)
        except Exception:
            tz = timezone.utc
        times = record.get('timestamp') or []
        indicators = record['indicators']
        candles = indicators['quote'][0]
        adjusted = (indicators.get('adjclose') or [{}])[0].get('adjclose') or []
        rows = []
        for i, stamp in enumerate(times):
            try:
                close = candles['close'][i]
                adj = adjusted[i] if i < len(adjusted) else None
                if close is None or float(close)<=0: continue
                multiplier = float(adj)/float(close) if adj is not None and float(adj)>0 else 1.0
                values={key:float(candles[key][i])*multiplier for key in ('open','high','low','close')}
                if not all(math.isfinite(v) and v>0 for v in values.values()): continue
                volume = int(candles['volume'][i] or 0)
                day = datetime.fromtimestamp(int(stamp), tz=tz).date()
                rows.append({'trading_date': day, **values, 'volume':max(volume,0)})
            except (IndexError,ValueError,TypeError,OverflowError,KeyError):
                continue
        if not rows:
            raise MarketDataError(f'No valid price candles returned for {symbol}.')
        return name,currency,rows
    except MarketDataError:
        raise
    except (KeyError,IndexError,TypeError,ValueError) as exc:
        raise MarketDataError(f'Unexpected market data format for {symbol} ({type(exc).__name__}).') from exc


def ensure_stock(db: Session, symbol: str, force: bool = False):
    stock = repo.get_stock(db, symbol)
    existing_prices = repo.list_prices(db, stock.id) if stock else []
    refreshed = stock.last_refreshed_at if stock else None
    if refreshed and refreshed.tzinfo is None:
        refreshed = refreshed.replace(tzinfo=timezone.utc)
    stale = not refreshed or (datetime.now(timezone.utc) - refreshed > timedelta(hours=12))
    if force or stale or not existing_prices:
        try:
            if symbol == 'DEMO':
                name, currency, rows = 'Demo Market · Synthetic Data', 'USD', demo_rows()
            else:
                name, currency, rows = _fetch_yahoo(symbol)
            stock = repo.save_prices(db, symbol, name, currency,
                                     'synthetic_demo' if symbol == 'DEMO' else 'yahoo_finance', rows)
            existing_prices = repo.list_prices(db, stock.id)
        except MarketDataError:
            # A cached series remains available during provider outage.
            if not existing_prices:
                raise
    return stock, existing_prices
