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


class TriageChangeOut(BaseModel):
    previous_attention_score: int | None = None
    previous_severity: Literal["Low", "Medium", "High"] | None = None
    previous_created_at: datetime | None = None
    score_delta: int = 0
    severity_changed: bool = False
    new_reasons: list[str] = Field(default_factory=list)
    removed_reasons: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)


class TriageItemOut(BaseModel):
    ticker: str
    status: Literal["ok", "not_checked", "data_issue"] = "ok"
    issue_message: str | None = None
    last_checked_at: datetime | None = None
    attention_score: int | None = Field(default=None, ge=0, le=100)
    severity: Literal["Low", "Medium", "High"] | None = None
    price: float | None = None
    price_change_pct: float | None = None
    as_of_date: date | None = None
    reasons: list[TriageReasonOut] = Field(default_factory=list)
    news: list[NewsArticleOut] = Field(default_factory=list)
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
    watch_note: WatchNoteOut
    changes: TriageChangeOut | None = None


class TriageResponse(BaseModel):
    generated_at: datetime
    items: list[TriageItemOut]
