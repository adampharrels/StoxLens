from datetime import datetime

from pydantic import BaseModel


class ReportListItem(BaseModel):
    id: str
    ticker: str
    created_at: datetime
    summary: str
    overall_view: str
