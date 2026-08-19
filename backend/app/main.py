from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from app.api.routes import candles, chart, compare, news, reports, research, triage, watchlist
from app.db.session import init_db

app = FastAPI(title="StoxLens", version="0.1.0")


def _cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(chart.router, prefix="/api/chart", tags=["chart"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(compare.router, prefix="/api/compare", tags=["compare"])
app.include_router(triage.router, prefix="/api/triage", tags=["triage"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(candles.router, prefix="/ws", tags=["candles"])
