from fastapi import APIRouter

router = APIRouter()


@router.get("")
def get_watchlist() -> list[dict[str, str]]:
    return [
        {"ticker": "AAPL", "signal": "↑ Positive"},
        {"ticker": "MSFT", "signal": "→ Neutral"},
        {"ticker": "IBM", "signal": "→ Neutral"},
    ]
