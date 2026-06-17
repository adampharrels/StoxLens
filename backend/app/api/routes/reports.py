from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db
from app.schemas.report import ReportListItem

router = APIRouter()


@router.get("", response_model=list[ReportListItem])
def list_reports(db: Session = Depends(get_db)) -> list[ReportListItem]:
    reports = db.query(models.ResearchReport).order_by(desc(models.ResearchReport.created_at)).limit(50).all()
    return [
        ReportListItem(
            id=str(report.id),
            ticker=report.ticker,
            created_at=report.created_at,
            summary=report.summary,
            overall_view=report.overall_view,
        )
        for report in reports
    ]
