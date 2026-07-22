from datetime import datetime

from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=24, pattern=r"^[A-Za-z.\-]+$")


class WatchlistItemOut(BaseModel):
    ticker: str
    signal: str
    created_at: datetime
