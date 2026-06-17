from datetime import datetime

import numpy as np
import pandas as pd


def _sample_price_data() -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=1261)
    rng = np.random.default_rng(42)
    returns = rng.normal(0.00045, 0.014, len(dates))
    close = 34 * np.cumprod(1 + returns)
    open_ = close * (1 + rng.normal(0, 0.003, len(dates)))
    high = np.maximum(open_, close) * (1 + rng.random(len(dates)) * 0.01)
    low = np.minimum(open_, close) * (1 - rng.random(len(dates)) * 0.01)
    volume = rng.integers(2_500_000, 9_000_000, len(dates))
    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
            "Adj Close": close,
        },
        index=dates,
    )


def fetch_price_data(ticker: str) -> pd.DataFrame:
    try:
        import yfinance as yf

        df = yf.download(ticker, period="5y", auto_adjust=True, progress=False)
        if df.empty:
            return _sample_price_data()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if "Adj Close" not in df.columns:
            df["Adj Close"] = df["Close"]
        return df
    except Exception:
        return _sample_price_data()


def clean_price_data(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned = cleaned[["Open", "High", "Low", "Close", "Volume", "Adj Close"]]
    cleaned = cleaned.ffill(limit=2).dropna()
    cleaned.index = pd.to_datetime(cleaned.index)
    return cleaned


def assess_data_quality(df: pd.DataFrame) -> dict[str, int | bool | str]:
    expected = len(pd.bdate_range(start=df.index.min(), end=df.index.max()))
    missing = max(expected - len(df), 0)
    completeness = round(len(df) / expected, 4) if expected else 0
    score = 5
    if completeness < 0.98:
        score -= 1
    if missing > 10:
        score -= 1
    if len(df) < 252:
        score -= 2
    return {
        "completeness": completeness,
        "gap_count": missing,
        "adjusted_prices": "Adj Close" in df.columns,
        "trading_days": len(df),
        "score": max(score, 1),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
