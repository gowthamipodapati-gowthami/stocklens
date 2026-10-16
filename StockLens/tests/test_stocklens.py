"""StockLens unit and integration suite. No external market data network needed."""
import math
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.main import app
from backend.app import models, repositories
from backend.app.services.analytics import calculate_dashboard
from backend.app.services.forecast import calculate_forecast, ForecastUnavailable
from backend.app.services.market_data import demo_rows, _fetch_yahoo


class AnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prices = [SimpleNamespace(**p) for p in demo_rows()]

    def test_daily_history_calculation(self):
        d = calculate_dashboard(self.prices, '5y')
        self.assertGreater(d['total_sessions'], 1800)
        self.assertGreater(len(d['history']), 1000)
        self.assertEqual(d['last_date'], self.prices[-1].trading_date.isoformat())
        self.assertGreater(d['high_52w'], d['low_52w'])
        self.assertLessEqual(d['max_drawdown_pct'], 0)
        self.assertTrue(math.isfinite(d['annualized_volatility_pct']))
        self.assertTrue(any(record['sma50'] is not None for record in d['history']))

    def test_period_filter(self):
        one = calculate_dashboard(self.prices, '1y')
        five = calculate_dashboard(self.prices, '5y')
        self.assertLess(len(one['history']), len(five['history']))
        self.assertEqual(one['latest_close'], five['latest_close'])

    def test_forecast_valid_and_ordered(self):
        f = calculate_forecast(self.prices, 30)
        self.assertEqual(len(f['points']), 30)
        self.assertGreater(f['validation_points'], 0)
        self.assertTrue(math.isfinite(f['mae']))
        for p in f['points']:
            self.assertLess(p['lower'], p['predicted'])
            self.assertLess(p['predicted'], p['upper'])
            self.assertGreater(p['date'], self.prices[-1].trading_date)
        self.assertLess(f['points'][0]['upper']/f['points'][0]['lower'], f['points'][-1]['upper']/f['points'][-1]['lower'])

    def test_not_enough_data(self):
        with self.assertRaises(ForecastUnavailable):
            calculate_forecast(self.prices[:60], 7)

    def test_persistence_on_sqlite(self):
        test_engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(test_engine)
        with Session(test_engine) as db:
            records=demo_rows()[:105]
            stock=repositories.save_prices(db, 'UNIT', 'Unit test', 'USD', 'synthetic_demo', records)
            self.assertEqual(len(repositories.list_prices(db, stock.id)), 105)
            # Upserts must not duplicate (stock,day).
            repositories.save_prices(db,'UNIT','Unit test','USD','synthetic_demo',records)
            self.assertEqual(db.scalar(select(func.count(models.DailyPrice.id))),105)
        test_engine.dispose()

    @patch('requests.get')
    def test_yahoo_adjusted_prices(self, mock_get):
        mock_get.return_value.raise_for_status.return_value=None
        mock_get.return_value.json.return_value={'chart':{'error':None,'result':[{
            'meta':{'shortName':'Example Co','currency':'INR','exchangeTimezoneName':'Asia/Kolkata'},
            'timestamp':[1752441600,1752528000],
            'indicators':{'quote':[{'open':[100,110],'high':[104,114],
                                    'low':[98,108],'close':[102,112],'volume':[200,300]}],
                          'adjclose':[{'adjclose':[51,56]}]}
        }]}}
        name, currency, rows=_fetch_yahoo('TCS.NS')
        self.assertEqual(name,'Example Co')
        self.assertEqual(currency,'INR')
        self.assertEqual(len(rows),2)
        self.assertAlmostEqual(rows[0]['close'],51)
        self.assertAlmostEqual(rows[0]['open'],50)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None,None,None)

    def test_frontend_served(self):
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        self.assertIn('text/html',response.headers['content-type'])
        self.assertIn('StockLens',response.text)
        self.assertEqual(self.client.get('/assets/js/api.js').status_code,200)

    def test_health_and_symbols(self):
        self.assertEqual(self.client.get('/api/health').json()['status'],'ok')
        self.assertIn('DEMO',[i['symbol'] for i in self.client.get('/api/symbols').json()['symbols']])

    def test_dashboard_and_forecast_save_to_db(self):
        response=self.client.get('/api/stocks/DEMO/dashboard?period=5y')
        self.assertEqual(response.status_code,200,response.text[:200])
        data=response.json()
        self.assertEqual(data['source'],'synthetic_demo')
        self.assertGreater(data['total_sessions'],1900)
        forecast=self.client.get('/api/stocks/DEMO/forecast?days=7')
        self.assertEqual(forecast.status_code,200,forecast.text[:200])
        pred=forecast.json()
        self.assertEqual(len(pred['points']),7)
        self.assertGreater(pred['points'][-1]['upper'],pred['points'][-1]['lower'])
        repeated=self.client.get('/api/stocks/DEMO/forecast?days=7')
        self.assertEqual(pred['cached_at'], repeated.json()['cached_at'])

    def test_validation_errors(self):
        self.assertEqual(self.client.get('/api/stocks/NO_SYMBOL!/dashboard').status_code,422)
        self.assertEqual(self.client.get('/api/stocks/DEMO/dashboard?period=bad').status_code,422)
        self.assertEqual(self.client.get('/api/stocks/DEMO/forecast?days=91').status_code,422)
        self.assertEqual(self.client.get('/api/does-not-exist').status_code,404)

if __name__=='__main__':
    unittest.main()
