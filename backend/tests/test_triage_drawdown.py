import numpy as np
import pandas as pd
import pytest

from app.services.triage import score_ticker


def _frame(closes: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=len(closes))
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [value + 1 for value in closes],
            "Low": [value - 1 for value in closes],
            "Close": closes,
            "Adj Close": closes,
            "Volume": [1_000_000.0] * len(closes),
        },
        index=dates,
    )


def _reason_codes(df: pd.DataFrame) -> set[str]:
    return {reason.code for reason in score_ticker("TEST", df).reasons}


def test_recovered_drawdown_does_not_trigger() -> None:
    # Rally to 200, fall 30% to 140, then recover to within 3% of the high.
    closes = [*np.linspace(100, 200, 120), *np.linspace(200, 140, 40), *np.linspace(140, 195, 100)]
    item = score_ticker("TEST", _frame(closes))

    assert item.metrics["max_drawdown"] <= -0.29
    assert item.metrics["current_drawdown"] == pytest.approx(195 / 200 - 1)
    assert "drawdown" not in {reason.code for reason in item.reasons}


def test_current_drawdown_beyond_threshold_triggers() -> None:
    # Rally to 200, then drift down and stay about 25% below the high.
    closes = [*np.linspace(100, 200, 160), *np.linspace(200, 150, 100)]
    item = score_ticker("TEST", _frame(closes))

    drawdown = next(reason for reason in item.reasons if reason.code == "drawdown")
    assert item.metrics["current_drawdown"] == pytest.approx(-0.25)
    assert drawdown.detail == "Price is -25.0% below its 252-day high."


def test_drawdown_window_is_reported_for_short_history() -> None:
    # Free-tier Alpha Vantage returns ~100 days, so the message must not claim a 52-week window.
    closes = [*np.linspace(100, 200, 50), *np.linspace(200, 150, 50)]

    assert "drawdown" in _reason_codes(_frame(closes))
    detail = next(r.detail for r in score_ticker("TEST", _frame(closes)).reasons if r.code == "drawdown")
    assert detail.endswith("below its 100-day high.")
