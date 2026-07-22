from math import sqrt
from typing import Literal, TypedDict

import pandas as pd


class SignalResult(TypedDict):
    return_1m: float
    return_3m: float
    return_6m: float
    return_12m: float
    volatility_30d: float
    volatility_90d: float
    max_drawdown: float
    ma_signal: Literal["above_both", "above_50_only", "below_both"]
    rsi: float
    volume_trend: float
    momentum_score: int
    trend_score: int
    risk_score: int
    data_quality_score: int
    as_of_date: str


def _pct(close: pd.Series, periods: int) -> float:
    if len(close) <= periods + 1:
        periods = max(len(close) - 1, 1)
    return float((close.iloc[-1] / close.iloc[-(periods + 1)]) - 1)


def _score(values: list[bool]) -> int:
    return sum(1 for value in values if value)


def calculate_signals(df: pd.DataFrame) -> SignalResult:
    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)

    return_1m = _pct(close, 21)
    return_3m = _pct(close, 63)
    return_6m = _pct(close, 126)
    return_12m = _pct(close, 252)

    daily_returns = close.pct_change()
    volatility_30d = float(daily_returns.rolling(30, min_periods=20).std().iloc[-1] * sqrt(252))
    volatility_90d = float(daily_returns.rolling(90, min_periods=60).std().iloc[-1] * sqrt(252))
    rolling_max = close.rolling(252, min_periods=1).max()
    max_drawdown = float(((close / rolling_max) - 1).min())

    ma_50 = float(close.rolling(50, min_periods=1).mean().iloc[-1])
    ma_200 = float(close.rolling(200, min_periods=1).mean().iloc[-1])
    current = float(close.iloc[-1])
    if current > ma_50 and current > ma_200:
        ma_signal: Literal["above_both", "above_50_only", "below_both"] = "above_both"
    elif current > ma_50:
        ma_signal = "above_50_only"
    else:
        ma_signal = "below_both"

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    rsi_current = float(rsi.fillna(50).iloc[-1])

    volume_ma_90 = float(volume.rolling(90, min_periods=1).mean().iloc[-1])
    volume_trend = float((volume.iloc[-21:].mean() / volume_ma_90) - 1)

    momentum_score = _score([return_1m > 0, return_3m > 0, return_6m > 0, return_12m > 0, rsi_current < 70])
    trend_score = _score([current > ma_50, current > ma_200, ma_50 > ma_200, volume_trend > 0, return_3m > 0.03])
    risk_score = _score([volatility_30d < 0.35, volatility_90d < 0.35, max_drawdown > -0.25, rsi_current < 72, rsi_current > 30])

    return {
        "return_1m": return_1m,
        "return_3m": return_3m,
        "return_6m": return_6m,
        "return_12m": return_12m,
        "volatility_30d": volatility_30d,
        "volatility_90d": volatility_90d,
        "max_drawdown": max_drawdown,
        "ma_signal": ma_signal,
        "rsi": rsi_current,
        "volume_trend": volume_trend,
        "momentum_score": momentum_score,
        "trend_score": trend_score,
        "risk_score": risk_score,
        "data_quality_score": 5,
        "as_of_date": str(df.index[-1].date()),
    }
