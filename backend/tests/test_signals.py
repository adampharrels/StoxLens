import pandas as pd
import pytest

from app.services.signals import _pct, calculate_signals


def _price_frame(days: int = 260) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=days)
    closes = [float(index + 100) for index in range(days)]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [value + 1 for value in closes],
            "Low": [value - 1 for value in closes],
            "Close": closes,
            "Adj Close": closes,
            "Volume": [1_000_000 + index for index in range(days)],
        },
        index=dates,
    )


def test_pct_uses_true_n_period_prior_close() -> None:
    close = pd.Series([100.0, 110.0, 121.0])

    assert _pct(close, 1) == pytest.approx(0.1)
    assert _pct(close, 2) == pytest.approx(0.21)


def test_calculate_signals_returns_use_expected_lookback_points() -> None:
    df = _price_frame()
    signals = calculate_signals(df)
    close = df["Close"]

    assert signals["return_1m"] == pytest.approx((close.iloc[-1] / close.iloc[-22]) - 1)
    assert signals["return_3m"] == pytest.approx((close.iloc[-1] / close.iloc[-64]) - 1)
    assert signals["return_6m"] == pytest.approx((close.iloc[-1] / close.iloc[-127]) - 1)
    assert signals["return_12m"] == pytest.approx((close.iloc[-1] / close.iloc[-253]) - 1)
