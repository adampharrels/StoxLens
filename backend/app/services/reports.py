from datetime import date
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.research import BriefPayload, ResearchReportOut, SignalSnapshotOut


def save_report(
    db: Session,
    ticker: str,
    signals: dict[str, Any],
    brief: BriefPayload,
    metadata: dict[str, str],
) -> models.ResearchReport:
    snapshot = models.SignalSnapshot(
        ticker=ticker.upper(),
        as_of_date=date.fromisoformat(str(signals["as_of_date"])),
        return_1m=signals["return_1m"],
        return_3m=signals["return_3m"],
        return_6m=signals["return_6m"],
        return_12m=signals["return_12m"],
        volatility_30d=signals["volatility_30d"],
        volatility_90d=signals["volatility_90d"],
        max_drawdown=signals["max_drawdown"],
        ma_signal=signals["ma_signal"],
        rsi=signals["rsi"],
        volume_trend=signals["volume_trend"],
        momentum_score=signals["momentum_score"],
        trend_score=signals["trend_score"],
        risk_score=signals["risk_score"],
        data_quality_score=signals["data_quality_score"],
    )
    db.add(snapshot)
    db.flush()
    report = models.ResearchReport(
        ticker=ticker.upper(),
        signal_snapshot_id=snapshot.id,
        summary=brief.summary,
        positive_signals=brief.positive_signals,
        negative_signals=brief.negative_signals,
        risks=brief.risks,
        data_quality_notes=brief.data_quality_notes,
        questions_for_research=brief.questions_for_research,
        overall_view=brief.overall_view,
        model_used=metadata["model_used"],
        prompt_version=metadata["prompt_version"],
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def latest_report(db: Session, ticker: str) -> models.ResearchReport | None:
    return (
        db.query(models.ResearchReport)
        .filter(models.ResearchReport.ticker == ticker.upper())
        .order_by(desc(models.ResearchReport.created_at))
        .first()
    )


def report_to_schema(report: models.ResearchReport) -> ResearchReportOut:
    signal = SignalSnapshotOut.model_validate(
        {
            "return_1m": report.signal_snapshot.return_1m,
            "return_3m": report.signal_snapshot.return_3m,
            "return_6m": report.signal_snapshot.return_6m,
            "return_12m": report.signal_snapshot.return_12m,
            "volatility_30d": report.signal_snapshot.volatility_30d,
            "volatility_90d": report.signal_snapshot.volatility_90d,
            "max_drawdown": report.signal_snapshot.max_drawdown,
            "ma_signal": report.signal_snapshot.ma_signal,
            "rsi": report.signal_snapshot.rsi,
            "volume_trend": report.signal_snapshot.volume_trend,
            "momentum_score": report.signal_snapshot.momentum_score,
            "trend_score": report.signal_snapshot.trend_score,
            "risk_score": report.signal_snapshot.risk_score,
            "data_quality_score": report.signal_snapshot.data_quality_score,
            "as_of_date": report.signal_snapshot.as_of_date,
        }
    )
    return ResearchReportOut(
        id=str(report.id),
        ticker=report.ticker,
        summary=report.summary,
        positive_signals=report.positive_signals,
        negative_signals=report.negative_signals,
        risks=report.risks,
        data_quality_notes=report.data_quality_notes,
        questions_for_research=report.questions_for_research,
        overall_view=report.overall_view,
        model_used=report.model_used,
        prompt_version=report.prompt_version,
        created_at=report.created_at,
        signal_snapshot=signal,
    )
