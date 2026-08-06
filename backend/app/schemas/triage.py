from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TriageReasonOut(BaseModel):
    code: str
    label: str
    detail: str
    impact: int = Field(ge=1, le=4)


class TriageItemOut(BaseModel):
    ticker: str
    attention_score: int = Field(ge=0, le=100)
    severity: Literal["Low", "Medium", "High"]
    price: float
    price_change_pct: float
    as_of_date: date
    reasons: list[TriageReasonOut]
    metrics: dict[str, float | int | str]


class TriageResponse(BaseModel):
    generated_at: datetime
    items: list[TriageItemOut]
