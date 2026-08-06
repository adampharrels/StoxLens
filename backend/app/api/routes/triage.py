from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.triage import TriageResponse
from app.services.triage import build_triage

router = APIRouter()


@router.get("", response_model=TriageResponse)
def get_triage(tickers: str | None = None, db: Session | None = Depends(get_db)) -> TriageResponse:
    return build_triage(db, tickers)
