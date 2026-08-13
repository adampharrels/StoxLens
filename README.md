# StoxLens

[![CI](https://github.com/adampharrels/StoxLens/actions/workflows/ci.yml/badge.svg)](https://github.com/adampharrels/StoxLens/actions/workflows/ci.yml)

StoxLens is a full-stack equity research workspace for managing a watchlist, ranking which stocks need attention, calculating price-based signals, comparing tickers, and generating structured research briefs.

The app is built as an internal analyst tool, not a marketing site. The frontend is Next.js and Tailwind CSS. The backend is FastAPI, pandas, SQLAlchemy, Alpha Vantage market data, Yahoo Finance fallback endpoints, and optional Anthropic brief generation.

## Features

- CRUD watchlist for saved tickers
- Today page that ranks watchlist stocks by attention urgency
- Five-year price history fetched from Alpha Vantage when configured
- Momentum, trend, volatility, drawdown, RSI, and volume-trend signals
- News-aware triage using Alpha Vantage news sentiment plus deterministic relevance rules
- Structured AI research brief generation
- Compare table across multiple tickers
- Reports list for generated briefs
- Docker Compose setup with PostgreSQL
- Local development mode without requiring SQLite or Postgres

## Project Structure

```text
backend/
  app/
    api/routes/        FastAPI route handlers
    services/          market data, signals, LLM, reports
    db/                SQLAlchemy models and session setup
    schemas/           Pydantic response models
  requirements.txt

frontend/
  app/                 Next.js app routes
  components/          UI components
  lib/                 API client, types, format helpers
  package.json

docker-compose.yml
```

## Run With Docker

```bash
docker compose up --build
```

Then open:

```text
http://localhost:3000
```

Backend API:

```text
http://localhost:8000
```

## Run Locally

Start the backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The backend automatically loads the root `.env` file.

Start the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## Environment Variables

Optional AI brief generation:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

Recommended market data provider:

```bash
export ALPHAVANTAGE_API_KEY=your_key_here
```

The same Alpha Vantage key is also used for optional news-aware triage. If no key is set, StoxLens still ranks watchlist tickers from price and technical signals; news reasons simply remain empty.

By default, StoxLens requests Alpha Vantage `TIME_SERIES_DAILY` with `outputsize=compact`, which works with free keys but returns a shorter history window. If you have a premium plan, set:

```bash
export ALPHAVANTAGE_OUTPUTSIZE=full
```

The API never returns fake prices. If the configured provider cannot return enough price history, StoxLens returns the provider/validation message.

Optional database URL:

```bash
export DATABASE_URL=postgresql://stoxlens:stoxlens@localhost:5432/stoxlens
```

If `DATABASE_URL` is not set, the backend uses in-memory report storage for local development. That means generated reports reset when the backend restarts.

## Ticker Format

StoxLens uses Alpha Vantage when `ALPHAVANTAGE_API_KEY` is configured. If no Alpha Vantage key is set, it falls back to Yahoo Finance HTTP endpoints.

US tickers usually have no suffix:

```text
AAPL
MSFT
IBM
```

Alpha Vantage uses exchange suffixes for many international symbols. StoxLens attempts to normalize common Yahoo ASX symbols automatically:

```text
BHP.AX    entered in StoxLens -> BHP.AUS sent to Alpha Vantage
CBA.AX    entered in StoxLens -> CBA.AUS sent to Alpha Vantage
```

Other symbols are sent through unchanged:

```text
AAPL
MSFT
IBM
TSCO.LON
SHOP.TRT
```

Provider coverage still applies. If Alpha Vantage has no daily data for a normalized symbol, StoxLens falls back to Yahoo Finance for that request. For BHP specifically, Alpha Vantage may provide the US listing as `BHP` even when ASX `BHP.AX` is unavailable.

The market data provider code is in:

```text
backend/app/services/market_data.py
```

```python
requests.get("https://www.alphavantage.co/query", ...)
```

## Company Metadata

Company metadata uses Alpha Vantage `OVERVIEW` when `ALPHAVANTAGE_API_KEY` is configured. Without the key, metadata falls back to Yahoo Finance quote data.

```text
backend/app/services/market_data.py
```

```python
requests.get("https://www.alphavantage.co/query", ...)
```

If metadata is unavailable, StoxLens still uses the ticker as the display name. Price data is not faked: if the configured provider returns no price history, the API returns an error instead of generated sample data.

## API Endpoints

```text
GET  /health
GET  /api/research/{ticker}
POST /api/research/{ticker}/generate
GET  /api/reports
GET  /api/watchlist
POST /api/watchlist
PUT  /api/watchlist/{ticker}
DELETE /api/watchlist/{ticker}
GET  /api/compare
GET  /api/triage
GET  /api/news/{ticker}
```

## Watchlist Triage Workflow

The practical workflow is:

```text
1. Add tickers on /watchlist
2. Open /today
3. Backend loads the saved watchlist
4. Backend fetches recent price data for each ticker
5. Backend fetches recent price-relevant news when ALPHAVANTAGE_API_KEY is configured
6. StoxLens ranks tickers by attention score and explains the trigger reasons
```

Technical triggers include moving-average breaks, RSI extremes, volatility spikes, drawdown thresholds, abnormal volume, unusual daily moves, and weak data quality.

News triggers are deterministic keyword categories. Current API category values are:

```text
earnings, guidance, regulatory, m&a, analyst, capital return, management, product
```

These categories are implementation-owned and can be expanded or renamed as the backend classifier evolves.

The goal is not to predict price direction. The goal is to answer:

```text
Which watchlist stocks deserve attention today, and why?
```

## Testing And CI

Backend checks:

```bash
cd backend
python -m compileall app
python -m pytest
```

Frontend checks:

```bash
cd frontend
npm run type-check
npm run build
```

GitHub Actions runs these checks on every push and pull request.

## Troubleshooting

If the frontend says:

```text
Backend unavailable. Start the FastAPI service on port 8000 to load live data.
```

Start the backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check the backend:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

If port `8000` is already in use, stop the existing process or run the backend on another port and update:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8001
```

for the frontend.
