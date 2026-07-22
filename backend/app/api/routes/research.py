from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.research import ResearchResponse
from app.services.rate_limit import RateLimitExceeded, check_rate_limit
from app.services.research import generate_research_snapshot, get_research_snapshot

router = APIRouter()


@router.post("/{ticker}/generate", response_model=ResearchResponse)
def generate_research(ticker: str, request: Request, db: Session | None = Depends(get_db)) -> ResearchResponse:
    client_host = request.client.host if request.client else "unknown"
    try:
        check_rate_limit(f"research-generate:{client_host}:{ticker.upper()}")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=f"Research generation limit reached. Try again in {exc.retry_after_seconds} seconds.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    return generate_research_snapshot(ticker, db)


@router.get("/{ticker}", response_model=ResearchResponse)
def get_research(ticker: str, db: Session | None = Depends(get_db)) -> ResearchResponse:
    return get_research_snapshot(ticker, db)
