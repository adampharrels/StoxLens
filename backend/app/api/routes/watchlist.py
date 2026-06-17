from fastapi import APIRouter

router = APIRouter()


@router.get("")
def get_watchlist() -> list[dict[str, str]]:
    return [
        {"ticker": "BHP.AX", "signal": "↑ Positive"},
        {"ticker": "CBA.AX", "signal": "→ Neutral"},
        {"ticker": "RIO.AX", "signal": "↓ Weak"},
    ]
