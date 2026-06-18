from fastapi import APIRouter, HTTPException

from app.services.market_data import (
    InsufficientPriceDataError,
    MarketDataError,
    RateLimitError,
    TickerNotFoundError,
    assess_data_quality,
    clean_price_data,
    fetch_price_data,
)
from app.services.signals import calculate_signals

router = APIRouter()


@router.get("")
def compare(tickers: str = "AAPL") -> dict[str, dict]:
    result: dict[str, dict] = {}
    for ticker in [item.strip().upper() for item in tickers.split(",") if item.strip()]:
        try:
            df = clean_price_data(fetch_price_data(ticker))
        except TickerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InsufficientPriceDataError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RateLimitError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except MarketDataError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        signals = calculate_signals(df)
        quality = assess_data_quality(df)
        signals["data_quality_score"] = int(quality["score"])
        result[ticker] = signals
    return result
