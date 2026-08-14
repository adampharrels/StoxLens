from datetime import datetime

from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=24, pattern=r"^[A-Za-z.\-]+$")
    watch_reason: str = Field(default="", max_length=600)
    main_risk: str = Field(default="", max_length=600)
    change_my_mind: str = Field(default="", max_length=600)


class WatchlistItemOut(BaseModel):
    ticker: str
    signal: str
    watch_reason: str
    main_risk: str
    change_my_mind: str
    created_at: datetime
