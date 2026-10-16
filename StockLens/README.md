# StockLens — Multi-Year Stock Analysis & Predictions

A runnable full-stack web dashboard with **separate UI, REST backend, database persistence, historical analytics, and predictive model**. The app starts on a clearly-labeled synthetic DEMO stock so it works even if Yahoo Finance is inaccessible. Enter `AAPL`, `MSFT`, `NVDA`, `RELIANCE.NS`, `TCS.NS`, `INFY.NS`, etc. for real historical data when the provider is available.

> **Status:** The bundled DEMO API and SQLite workflow are tested. The Supabase SQL file and deployment configuration are supplied but a real Supabase project has **not** been provisioned for you. Enter your own secret database connection to activate it. Yahoo Finance live network retrieval needs internet connectivity and can occasionally be throttled or interrupted.

## Features

- Search stocks via their **Yahoo Finance ticker** (US and Indian NSE symbols supported).
- Historical OHLCV prices, **1-year, 3-year, 5-year, 10-year, and all-available** ranges, 50-day moving average and volume.
- Latest available daily adjusted close, price change, price trend relative to 50-day SMA.
- CAGR, period return, annualized historical volatility, max drawdown, 52-week high/low, 30-day average volume.
- Calendar-year returns chart with each year separately summarized.
- Experimental 7-, 30-, or 90-**weekday** ahead predictions, central trajectory, heuristic uncertainty band, and holdout model-vs-naive errors.
- Forecasts, their model metrics, price history and ticker metadata saved to SQLite or Supabase PostgreSQL.
- Fully responsive, dark financial dashboard with interactive SVG tooltips (no frontend frameworks or external chart CDN).
- **`DEMO` is deterministic synthetic data**, never presented as real prices.
- Swagger API available at `/docs`.

## Folder structure / separation of responsibilities

```text
StockLens/
├── frontend/
│   ├── index.html             # Semantic UI markup ONLY
│   ├── styles.css             # Layout and visual styles
│   └── js/
│       ├── api.js             # HTTP client ONLY
│       ├── charts.js          # SVG chart rendering ONLY
│       └── app.js             # UI state/events ONLY
├── backend/app/
│   ├── main.py                # API routes + static frontend hosting
│   ├── database.py            # SQLAlchemy engine, DB sessions
│   ├── models.py              # Relational tables
│   ├── repositories.py        # Database queries and persistence
│   └── services/
│       ├── market_data.py     # Yahoo data client, DEMO generator
│       ├── analytics.py       # Pure historical calculations
│       └── forecast.py        # Pure model training/forecast
├── data/                      # Bundled local SQLite demo DB
├── supabase/schema.sql        # Cloud Postgres tables, constraints, RLS
├── tests/                     # Automated backend/integration tests
├── .env.example               # Copy to .env to configure Supabase
├── requirements.txt
├── Dockerfile
├── render.yaml
├── start_windows.bat
└── start_linux.sh
```

**Flow:** Browser → FastAPI routes (`/api/*`) → service layer → repository → PostgreSQL/SQLite. No database credentials, SQL, Python, model logic, nor Supabase keys are embedded in browser assets. All models train on the backend.

## Option A — Run immediately on Windows (SQLite, easiest)

1. Install **Python 3.12** (or another supported Python 3.10+; 3.12 recommended) with `pip` and internet access for package installation.
2. Extract this ZIP to a folder, e.g. `C:\\Projects\\StockLens`.
3. Double-click **`start_windows.bat`** (installs requirements into `.venv`, then starts the server).
4. Open **http://127.0.0.1:8000**.
5. See the synthetic DEMO immediately. Enter `AAPL` or `RELIANCE.NS` and click **Analyze stock** for real Yahoo history, if reachable.
6. Open **http://127.0.0.1:8000/docs** for Swagger API testing.

PowerShell alternative (start from the extracted root):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000
```

If PowerShell blocks activation, use `.venv\\Scripts\\python.exe -m pip install -r requirements.txt` and `.venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --reload --port 8000` without activating.

### macOS / Linux

```bash
bash start_linux.sh
# http://127.0.0.1:8000
```

## Option B — Use Supabase PostgreSQL backend

This is a **server-side database connection**, not a browser-based Supabase client. It doesn't need the Supabase anon key or publishable key.

1. Create a Supabase project at [supabase.com](https://supabase.com).
2. Open **SQL Editor** → **New query**, paste **`supabase/schema.sql`**, and **Run**. Creates four tables and indexes, enables Row Level Security and revokes `anon` and `authenticated` table privileges. The backend's privileged Postgres connection can still access the tables; do not expose the database password to the browser.
3. In Supabase click **Connect** → **Session pooler** (port **5432**) if using a server with only IPv4 connectivity. For always-on IPv6-enabled backends, a **Direct connection** works too. **Copy the actual connection URI**; don't guess its host or username. The transaction pooler on port **6543** is supported with `NullPool` when needed.
4. Copy `.env.example` to `.env` in the ZIP root. Set `DATABASE_URL` to your PostgreSQL connection URI. Example shape (**placeholder only**):

```env
DATABASE_URL=postgresql://postgres.PROJECT_REF:YOUR_URL_ENCODED_PASSWORD@YOUR_ACTUAL_POOLER_HOST:5432/postgres?sslmode=require
```

5. Start the app as above. The backend creates any missing tables with SQLAlchemy on startup and stores new histories/forecasts in Supabase. Data becomes visible under **Table Editor** (`stocks`, `daily_prices`, `forecast_runs`, `forecast_points`) after analyzing a stock.
6. Test **http://127.0.0.1:8000/api/health**. It should show `"database":"postgresql"` when configured.

**Supabase nuances:** If a database password contains `@`, `#`, `&`, `?` or spaces, percent-encode the password part. Session pooling on port 5432 is often easiest for long-running Python servers; transaction pooling on 6543 is an option for short-lived/serverless instances. Keep `.env` private and never commit it. `sslmode=require` is set automatically for PostgreSQL URLs unless you explicitly supply your own SSL mode. For a more stringent production setup, verify the server certificate as described in Supabase docs. Startup table creation does not automatically enable RLS; **execute `supabase/schema.sql`** to apply security settings.

## Deploy on Render (Docker)

1. Upload the extracted project to a private GitHub repository. Do not commit `.env`.
2. Create a Supabase project and execute `supabase/schema.sql` as above.
3. In [Render](https://render.com) create a new **Web Service** from the repository (Docker environment), or use the supplied `render.yaml` Blueprint.
4. Add the Render environment variable **`DATABASE_URL`** with your **actual** Supabase database URL (`sslmode=require`).
5. Deploy. Your app is served by FastAPI on the `PORT` supplied by Render. Open the URL, then `/api/health` and `/docs` to verify.

**Important:** Do not rely on local SQLite for long-lived hosting on ephemeral containers; use Supabase or a durable PostgreSQL service to retain histories and predictions between deployments. On first use of a symbol the server must reach Yahoo Finance from Render. Some network providers throttle free historical-data endpoints. For production/financial use, switch to a properly licensed market-data API.

## API examples

| Endpoint | Result |
| --- | --- |
| `GET /api/health` | Server status + database type |
| `GET /api/symbols` | Built-in ticker examples |
| `GET /api/stocks/DEMO/dashboard?period=5y` | Complete metrics, historical daily prices, annual returns |
| `GET /api/stocks/AAPL/dashboard?period=10y` | Real historical data via Yahoo Finance when available |
| `GET /api/stocks/TCS.NS/forecast?days=30` | 30-weekday model projection, backtest MAE, band |
| `GET /docs` | Interactive Swagger API explorer |

**Supported period values:** `1y`, `3y`, `5y`, `10y`, `all`. The backend fetches up to approximately ten years of historical daily bars for real stocks; `all` means all currently cached data (typically ten years; DEMO has eight years). Stock histories are refreshed if older than 12 hours, or force refresh by adding `&refresh=true` to the dashboard URL. Forecasts are cached by ticker, latest trading date and horizon for 12 hours.

## Database relationships

```text
stocks 1 ---- * daily_prices
   |
   +--- 1 ---- * forecast_runs 1 ---- * forecast_points
```

- `stocks`: company/ticker metadata, source and last refresh timestamp.
- `daily_prices`: unique `(stock_id, trading_date)` OHLCV, historical archive.
- `forecast_runs`: prediction horizon, training model, as-of date, validation errors.
- `forecast_points`: ordered `(date, predicted, lower, upper)` for each saved run.

## Modeling and limitations

`backend/app/services/forecast.py` trains a **regularized Ridge regression on lagged log-return features** (recent 1/3/5/10/20-day returns, volatility and momentum). Inputs at date *t* only use information available on or before *t*. The final 20–60 observed one-day samples are reserved for chronological validation, producing **MAE**, **RMSE**, and a **random-walk/last-close naive baseline MAE**. The model is then re-fit on all observed history to recursively forecast the next 7/30/90 **weekdays**. Uncertainty bands widen by `1.96 × validation residual volatility × sqrt(horizon)`, in log space.

This is an educational demonstration, **not a calibrated probabilistic forecast or a reliable way to beat the market**. The band is heuristic and can miss real outcomes; forecasts can have *worse* holdout error than the naive baseline. Market behavior, corporate actions, macro events, exchange holidays and data revisions are not modeled. Real historical adjusted OHLC may be different from raw daily exchange OHLC. Calendar-year returns are end-of-year adjusted close-to-close (first partial year uses first available close). Historical CAGR is from the first stored observation to the most recent. The data provider is unofficial and no intraday quote freshness is guaranteed.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests use only synthetic fixtures / mocked upstream responses, so no real market-data network is required. The UI is dependency-free HTML/CSS/JS; only the backend requires the Python packages.

## Useful references

- [Supabase: choosing a Postgres connection / pooler](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase: Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Render: Blueprint specification](https://render.com/docs/blueprint-spec)
- [Yahoo Finance chart endpoint (unofficial)](https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=1mo&interval=1d)

**No financial recommendations. No Supabase project is created automatically without your private project details.**
