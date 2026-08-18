from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.research import PricePoint
from app.services.research import saved_price_history

router = APIRouter()

RANGE_LIMITS = {
    "1m": 21,
    "3m": 63,
    "6m": 126,
    "1y": 252,
}


@router.get("/{ticker}", response_model=list[PricePoint])
def get_chart(
    ticker: str,
    range: str = Query(default="1y", pattern="^(1m|3m|6m|1y)$"),
    interval: str = Query(default="1d", pattern="^1d$"),
    db: Session | None = Depends(get_db),
) -> list[PricePoint]:
    # Chart requests read saved OHLC candles. Fresh provider fetches happen through /api/research/{ticker}/run.
    df = saved_price_history(db, ticker)
    if df is None:
        return []

    rows = df.tail(RANGE_LIMITS[range])
    return [
        PricePoint(
            date=index.date(),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=int(row["Volume"]),
            adj_close=float(row["Adj Close"]),
        )
        for index, row in rows.iterrows()
    ]
