from fastapi import APIRouter

from app.services.market_data import assess_data_quality, clean_price_data, fetch_price_data
from app.services.signals import calculate_signals

router = APIRouter()


@router.get("")
def compare(tickers: str = "BHP.AX,CBA.AX,RIO.AX") -> dict[str, dict]:
    result: dict[str, dict] = {}
    for ticker in [item.strip().upper() for item in tickers.split(",") if item.strip()]:
        df = clean_price_data(fetch_price_data(ticker))
        signals = calculate_signals(df)
        quality = assess_data_quality(df)
        signals["data_quality_score"] = int(quality["score"])
        result[ticker] = signals
    return result
