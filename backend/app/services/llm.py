import json
import os
from typing import Any

from app.schemas.research import BriefPayload

PROMPT_VERSION = "v2.1"
MODEL_USED = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

SYSTEM = """You are an investment research assistant generating structured quantitative research briefs.

Do not provide buy, sell, or hold recommendations.
Do not state price targets.
Focus on: what the data suggests, where signals may be weak, data quality limitations, and questions a human analyst should investigate.

Return only valid JSON. No preamble, no markdown, no explanation outside the JSON."""


def build_prompt(ticker: str, signals: dict[str, Any], quality: dict[str, Any]) -> str:
    return f"""Generate a structured research brief for {ticker}.

Signals:
{json.dumps(signals, indent=2)}

Data quality:
{json.dumps(quality, indent=2)}

Return JSON in this exact schema:
{{
  "summary": "string, 2-3 sentences",
  "positive_signals": ["string", ...],
  "negative_signals": ["string", ...],
  "risks": ["string", ...],
  "data_quality_notes": ["string", ...],
  "questions_for_research": ["string", ...],
  "overall_view": "Watchlist" | "Needs Review" | "Weak Signal"
}}"""


def _fallback_brief(ticker: str, signals: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any]:
    positive = signals["momentum_score"] >= 4 and signals["trend_score"] >= 3
    weak = signals["momentum_score"] <= 2 or signals["risk_score"] <= 2
    overall = "Watchlist" if positive else "Weak Signal" if weak else "Needs Review"
    return {
        "summary": (
            f"{ticker.upper()} shows a {overall.lower()} quantitative profile based on recent momentum, trend, "
            "risk, and data-quality inputs. The signal set should be treated as screening evidence for analyst review."
        ),
        "positive_signals": [
            "Price trend is above key moving-average thresholds" if signals["ma_signal"] == "above_both" else "Recent returns provide some support",
            f"12M return is {signals['return_12m'] * 100:.1f}%",
            f"Volume trend is {signals['volume_trend'] * 100:.1f}% versus the 90d average",
            f"RSI is not extreme at {signals['rsi']:.1f}",
        ],
        "negative_signals": [
            f"Max drawdown reached {signals['max_drawdown'] * 100:.1f}%",
            f"30d volatility is {signals['volatility_30d'] * 100:.1f}% annualised",
        ],
        "risks": [
            "Short-term market regime may change faster than trailing indicators",
            "Single-name research requires sector and balance-sheet context beyond price history",
            "Liquidity and event-risk conditions are not fully captured by the signal model",
        ],
        "data_quality_notes": [
            f"{quality['trading_days']} trading days available",
            f"{quality['gap_count']} expected business-day gaps identified",
            "Dividend-adjusted prices used where available",
        ],
        "questions_for_research": [
            "How do fundamentals compare with the current price trend?",
            "Are recent volume changes event-driven or structural?",
            "What scenarios would invalidate the observed momentum profile?",
        ],
        "overall_view": overall,
    }


def call_llm(prompt: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=MODEL_USED,
            max_tokens=1200,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception:
        return ""


def parse_and_validate_brief(response: str, ticker: str, signals: dict[str, Any], quality: dict[str, Any]) -> BriefPayload:
    payload = json.loads(response) if response else _fallback_brief(ticker, signals, quality)
    return BriefPayload.model_validate(payload)
