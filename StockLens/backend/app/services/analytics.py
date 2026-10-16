"""Pure price-series analytics. No database, HTTP, or UI dependencies."""
from datetime import timedelta
from math import sqrt
import numpy as np
import pandas as pd

VALID_PERIODS = {'1y':365, '3y':365*3, '5y':365*5, '10y':365*10, 'all':100*365}


def calculate_dashboard(prices: list, period: str) -> dict:
    if not prices:
        raise ValueError('No prices available')
    frame = pd.DataFrame([{'date':p.trading_date, 'open':p.open,'high':p.high,
                           'low':p.low,'close':p.close,'volume':p.volume} for p in prices])
    frame = frame.sort_values('date').reset_index(drop=True)
    close = frame['close'].astype(float)
    frame['sma20'] = close.rolling(20).mean()
    frame['sma50'] = close.rolling(50).mean()
    frame['sma200'] = close.rolling(200).mean()
    log_ret = np.log(close / close.shift(1)).replace([np.inf,-np.inf], np.nan)
    volatility = float(log_ret.tail(252).std() * sqrt(252) * 100) if len(close) >= 30 else None
    first = float(close.iloc[0]); last = float(close.iloc[-1])
    prior = float(close.iloc[-2]) if len(close) >= 2 else first
    delta = last - prior
    delta_pct = (last / prior - 1) * 100 if prior else 0.0
    days = max((frame['date'].iloc[-1] - frame['date'].iloc[0]).days, 1)
    cagr = ((last / first) ** (365.25/days) - 1)*100 if days >= 365 else None
    rolling_peaks = close.cummax()
    max_drawdown = float(((close / rolling_peaks - 1) * 100).min())
    last_year = frame[frame['date'] >= frame['date'].iloc[-1] - timedelta(days=365)]
    yearly = []
    for year, group in frame.groupby(frame['date'].map(lambda d:d.year)):
        # Calendar-year close-to-close return, using prior-year final close if available.
        idx = group.index[0]
        base = float(frame.loc[idx-1, 'close']) if idx > 0 else float(group['close'].iloc[0])
        ending = float(group['close'].iloc[-1])
        yearly.append({'year':int(year), 'return_pct':round((ending/base-1)*100,2),
                       'close':round(ending,2), 'sessions':int(len(group))})

    cutoff = frame['date'].iloc[-1] - timedelta(days=VALID_PERIODS[period])
    selected = frame[frame['date'] >= cutoff]
    period_return = float((selected['close'].iloc[-1] / selected['close'].iloc[0] - 1)*100)
    last_price = float(close.iloc[-1])
    ma50 = float(frame['sma50'].iloc[-1]) if len(frame) >= 50 else None
    trend = ('above' if last_price >= ma50 else 'below') if ma50 is not None else 'unavailable'
    rows = []
    for row in selected.itertuples(index=False):
        rows.append({'date':row.date.isoformat(), 'open':round(float(row.open),4),
                     'high':round(float(row.high),4), 'low':round(float(row.low),4),
                     'close':round(float(row.close),4), 'volume':int(row.volume),
                     'sma20':round(float(row.sma20),4) if pd.notna(row.sma20) else None,
                     'sma50':round(float(row.sma50),4) if pd.notna(row.sma50) else None,
                     'sma200':round(float(row.sma200),4) if pd.notna(row.sma200) else None})
    return {'latest_close':round(last_price,4), 'change':round(delta,4),
            'change_pct':round(delta_pct,2), 'period_return_pct':round(period_return,2),
            'first_date':frame['date'].iloc[0].isoformat(),
            'last_date':frame['date'].iloc[-1].isoformat(),
            'total_sessions':len(frame), 'visible_sessions':len(selected),
            'cagr_pct':round(cagr,2) if cagr is not None else None,
            'annualized_volatility_pct':round(volatility,2) if volatility is not None else None,
            'max_drawdown_pct':round(max_drawdown,2),
            'high_52w':round(float(last_year['high'].max()),4),
            'low_52w':round(float(last_year['low'].min()),4),
            'average_volume_30d':round(float(frame['volume'].tail(30).mean())),
            'sma50':round(ma50,4) if ma50 is not None else None,
            'trend_vs_sma50':trend,
            'years':yearly, 'history':rows}
