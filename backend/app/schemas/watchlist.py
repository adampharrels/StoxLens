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
    last_check_status: str | None = None
    last_check_message: str | None = None
    last_checked_at: datetime | None = None
    created_at: datetime
