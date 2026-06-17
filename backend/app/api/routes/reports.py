from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.report import ReportListItem
from app.services.reports import list_report_items

router = APIRouter()


@router.get("", response_model=list[ReportListItem])
def list_reports(db: Session | None = Depends(get_db)) -> list[ReportListItem]:
    return [ReportListItem.model_validate(report) for report in list_report_items(db)]
