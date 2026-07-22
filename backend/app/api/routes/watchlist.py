from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.watchlist import WatchlistCreate, WatchlistItemOut
from app.services.watchlist import add_watchlist_item, list_watchlist, remove_watchlist_item

router = APIRouter()


@router.get("", response_model=list[WatchlistItemOut])
def get_watchlist(db: Session | None = Depends(get_db)) -> list[dict]:
    return list_watchlist(db)


@router.post("", response_model=WatchlistItemOut, status_code=status.HTTP_201_CREATED)
def create_watchlist_item(payload: WatchlistCreate, db: Session | None = Depends(get_db)) -> dict:
    return add_watchlist_item(db, payload.ticker)


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(ticker: str, db: Session | None = Depends(get_db)) -> Response:
    remove_watchlist_item(db, ticker)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
