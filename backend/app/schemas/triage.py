from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TriageReasonOut(BaseModel):
    code: str
    label: str
    detail: str
    impact: int = Field(ge=1, le=4)


class NewsArticleOut(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime
    category: str
    impact: int = Field(ge=1, le=4)


class WatchNoteOut(BaseModel):
    ticker: str
    watch_reason: str = ""
    main_risk: str = ""
    change_my_mind: str = ""


class TriageItemOut(BaseModel):
    ticker: str
    attention_score: int = Field(ge=0, le=100)
    severity: Literal["Low", "Medium", "High"]
    price: float
    price_change_pct: float
    as_of_date: date
    reasons: list[TriageReasonOut]
    news: list[NewsArticleOut]
    metrics: dict[str, float | int | str]
    watch_note: WatchNoteOut


class TriageResponse(BaseModel):
    generated_at: datetime
    items: list[TriageItemOut]
