from fastapi import APIRouter, HTTPException

from app.services.market_data import (
    InsufficientPriceDataError,
    MarketDataError,
    RateLimitError,
    TickerNotFoundError,
    assess_data_quality,
    clean_price_data,
    fetch_price_data,
    public_market_data_error,
)
from app.services.signals import calculate_signals

router = APIRouter()


@router.get("")
def compare(tickers: str = "AAPL") -> dict[str, dict]:
    result: dict[str, dict] = {}
    ticker_list = [item.strip().upper() for item in tickers.split(",") if item.strip()]
    if not ticker_list:
        raise HTTPException(status_code=422, detail="At least one ticker is required.")
    if len(ticker_list) > 8:
        raise HTTPException(status_code=422, detail="Compare supports up to 8 tickers at a time.")

    for ticker in ticker_list:
        try:
            df = clean_price_data(fetch_price_data(ticker))
        except TickerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InsufficientPriceDataError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RateLimitError as exc:
            raise HTTPException(status_code=429, detail=public_market_data_error(exc)) from exc
        except MarketDataError as exc:
            raise HTTPException(status_code=502, detail=public_market_data_error(exc)) from exc
        signals = calculate_signals(df)
        quality = assess_data_quality(df)
        signals["data_quality_score"] = int(quality["score"])
        result[ticker] = signals
    return result
