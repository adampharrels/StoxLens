from datetime import date, datetime
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.research import BriefPayload, ResearchReportOut, SignalSnapshotOut

_memory_reports: list[ResearchReportOut] = []


def _signal_schema(signals: dict[str, Any]) -> SignalSnapshotOut:
    return SignalSnapshotOut.model_validate(
        {
            "return_1m": signals["return_1m"],
            "return_3m": signals["return_3m"],
            "return_6m": signals["return_6m"],
            "return_12m": signals["return_12m"],
            "volatility_30d": signals["volatility_30d"],
            "volatility_90d": signals["volatility_90d"],
            "max_drawdown": signals["max_drawdown"],
            "ma_signal": signals["ma_signal"],
            "rsi": signals["rsi"],
            "volume_trend": signals["volume_trend"],
            "momentum_score": signals["momentum_score"],
            "trend_score": signals["trend_score"],
            "risk_score": signals["risk_score"],
            "data_quality_score": signals["data_quality_score"],
            "as_of_date": signals["as_of_date"],
        }
    )


def save_report(
    db: Session | None,
    ticker: str,
    signals: dict[str, Any],
    brief: BriefPayload,
    metadata: dict[str, str],
) -> models.ResearchReport | ResearchReportOut:
    if db is None:
        report = ResearchReportOut(
            id=str(len(_memory_reports) + 1),
            ticker=ticker.upper(),
            summary=brief.summary,
            positive_signals=brief.positive_signals,
            negative_signals=brief.negative_signals,
            risks=brief.risks,
            data_quality_notes=brief.data_quality_notes,
            questions_for_research=brief.questions_for_research,
            overall_view=brief.overall_view,
            model_used=metadata["model_used"],
            prompt_version=metadata["prompt_version"],
            created_at=datetime.utcnow(),
            signal_snapshot=_signal_schema(signals),
        )
        _memory_reports.append(report)
        return report

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


def latest_report(db: Session | None, ticker: str) -> models.ResearchReport | ResearchReportOut | None:
    if db is None:
        for report in reversed(_memory_reports):
            if report.ticker == ticker.upper():
                return report
        return None
    return (
        db.query(models.ResearchReport)
        .filter(models.ResearchReport.ticker == ticker.upper())
        .order_by(desc(models.ResearchReport.created_at))
        .first()
    )


def report_to_schema(report: models.ResearchReport | ResearchReportOut) -> ResearchReportOut:
    if isinstance(report, ResearchReportOut):
        return report
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


def list_report_items(db: Session | None) -> list[dict[str, Any]]:
    if db is None:
        return [
            {
                "id": report.id,
                "ticker": report.ticker,
                "created_at": report.created_at,
                "summary": report.summary,
                "overall_view": report.overall_view,
            }
            for report in reversed(_memory_reports[-50:])
        ]

    reports = db.query(models.ResearchReport).order_by(desc(models.ResearchReport.created_at)).limit(50).all()
    return [
        {
            "id": str(report.id),
            "ticker": report.ticker,
            "created_at": report.created_at,
            "summary": report.summary,
            "overall_view": report.overall_view,
        }
        for report in reports
    ]
