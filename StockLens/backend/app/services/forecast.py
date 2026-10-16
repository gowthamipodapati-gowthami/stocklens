"""Exploratory one-day-return Ridge forecast, walk-forward-like chronological holdout.
Not investment advice; illustrative uncertainty bands assume approximate daily residual independence.
"""
from math import sqrt
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MODEL_NAME = 'Ridge · autoregressive daily returns v1'

class ForecastUnavailable(Exception):
    pass


def feature_at(closes: np.ndarray) -> list[float]:
    # Only data known as of the forecast origin; next day's return is the target.
    r = np.diff(np.log(closes[-27:]))
    return [float(r[-1]), float(np.mean(r[-3:])), float(np.mean(r[-5:])),
            float(np.mean(r[-10:])), float(np.mean(r[-20:])),
            float(np.std(r[-5:])), float(np.std(r[-20:])),
            float(np.log(closes[-1]/closes[-6])),
            float(np.log(closes[-1]/closes[-21]))]


def calculate_forecast(prices: list, days: int) -> dict:
    if not 1 <= days <= 90:
        raise ValueError('Prediction horizon must be between 1 and 90 trading days')
    closes = np.asarray([float(p.close) for p in prices], dtype=float)
    if len(closes) < 95 or np.any(closes <= 0) or not np.all(np.isfinite(closes)):
        raise ForecastUnavailable('At least 95 valid trading sessions are required to produce a forecast.')

    X, y, origins = [], [], []
    for t in range(26, len(closes)-1):
        X.append(feature_at(closes[:t+1]))
        y.append(float(np.log(closes[t+1] / closes[t])))
        origins.append(t)
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    origins = np.asarray(origins, dtype=int)
    test_n = min(60, max(20, int(len(y) * 0.2)))
    if len(y) - test_n < 25:
        raise ForecastUnavailable('Insufficient training history.')
    model = make_pipeline(StandardScaler(), Ridge(alpha=20.0))
    model.fit(X[:-test_n], y[:-test_n])
    validation_pred = model.predict(X[-test_n:])
    validation_prices = closes[origins[-test_n:]] * np.exp(np.clip(validation_pred,-.08,.08))
    actual_prices = closes[origins[-test_n:]+1]
    previous_prices = closes[origins[-test_n:]]
    mae = float(np.mean(np.abs(validation_prices - actual_prices)))
    baseline_mae = float(np.mean(np.abs(previous_prices - actual_prices)))
    rmse = float(np.sqrt(np.mean((validation_prices-actual_prices)**2)))
    residuals = y[-test_n:] - validation_pred
    daily_sigma = max(float(np.std(residuals, ddof=1)), 0.002)

    # Retrain on all observed samples only after validation; no future data leakage.
    model.fit(X, y)
    observed = list(closes)
    last_close = float(closes[-1])
    dates = pd.bdate_range(start=pd.Timestamp(prices[-1].trading_date) + pd.Timedelta(days=1), periods=days)
    results = []
    for step, day in enumerate(dates, start=1):
        expected_log_return = float(np.clip(model.predict(np.asarray([feature_at(np.asarray(observed))]))[0], -0.08, 0.08))
        next_close = float(observed[-1] * np.exp(expected_log_return))
        observed.append(next_close)
        band = 1.96 * daily_sigma * sqrt(step)
        results.append({'date':day.date(), 'predicted':round(next_close,4),
                        'lower':round(next_close * np.exp(-band),4),
                        'upper':round(next_close * np.exp(band),4)})
    return {'model_name':MODEL_NAME, 'base_close':round(last_close,4),
            'mae':round(mae,4), 'baseline_mae':round(baseline_mae,4),
            'rmse':round(rmse,4), 'validation_points':test_n, 'points':results}
