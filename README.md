# StoxLens

StoxLens is a full-stack equity research workspace for screening stocks, calculating price-based signals, comparing tickers, and generating structured research briefs.

The app is built as an internal analyst tool, not a marketing site. The frontend is Next.js and Tailwind CSS. The backend is FastAPI, pandas, SQLAlchemy, direct Yahoo Finance HTTP endpoints, and optional Anthropic brief generation.

## Features

- Research page for any Yahoo Finance ticker
- Five-year price history fetched from Yahoo Finance
- Momentum, trend, volatility, drawdown, RSI, and volume-trend signals
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

Optional database URL:

```bash
export DATABASE_URL=postgresql://stoxlens:stoxlens@localhost:5432/stoxlens
```

If `DATABASE_URL` is not set, the backend uses in-memory report storage for local development. That means generated reports reset when the backend restarts.

## Ticker Format

StoxLens sends the ticker string directly to Yahoo Finance.

US tickers usually have no suffix:

```text
AAPL
MSFT
IBM
```

Many non-US exchanges use suffixes:

```text
BHP.AX    ASX
CBA.AX    ASX
7203.T    Tokyo
VOD.L     London
NESN.SW   Swiss
```

The Yahoo Finance chart call is in:

```text
backend/app/services/market_data.py
```

```python
requests.get("https://query1.finance.yahoo.com/v8/finance/chart/{ticker}", ...)
```

## Company Metadata

Price data and display metadata come from Yahoo Finance HTTP endpoints.

```text
backend/app/services/market_data.py
```

```python
requests.get("https://query1.finance.yahoo.com/v7/finance/quote", ...)
```

If Yahoo does not return metadata, StoxLens still uses the ticker as the display name. Price data is not faked: if Yahoo returns no price history, the API returns an error instead of generated sample data.

## API Endpoints

```text
GET  /health
GET  /api/research/{ticker}
POST /api/research/{ticker}/generate
GET  /api/reports
GET  /api/watchlist
GET  /api/compare
```

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
