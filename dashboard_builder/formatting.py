from __future__ import annotations

import pandas as pd

_PERCENT_KEYWORDS = ("rate", "risk", "margin", "rtp", "hold", "conversion", "retention", "churn")
_CURRENCY_KEYWORDS = (
    "ggr", "ngr", "deposit", "withdrawal", "volume", "fee", "wager", "handle", "payout",
    "ltv", "revenue", "value", "cpa", "spend", "bonus",
)


def infer_format(label: str) -> str:
    """Guess a display format ("percent" | "currency" | "number") from a metric label,
    matching the same heuristic already used by the AI Copilot's semantic engine so a metric
    formats identically everywhere it appears."""
    normalized = label.lower()
    if any(word in normalized for word in _PERCENT_KEYWORDS):
        return "percent"
    if any(word in normalized for word in _CURRENCY_KEYWORDS):
        return "currency"
    return "number"


def format_value(value, fmt: str, *, compact: bool = True, decimals: int | None = None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    number = float(value)
    if fmt == "percent":
        digits = decimals if decimals is not None else 1
        return f"{number * 100:.{digits}f}%"
    if fmt == "currency":
        sign = "-" if number < 0 else ""
        magnitude = abs(number)
        if compact and magnitude >= 1_000_000:
            return f"{sign}${magnitude / 1_000_000:.2f}M"
        if compact and magnitude >= 1_000:
            return f"{sign}${magnitude / 1_000:.1f}K"
        digits = decimals if decimals is not None else 0
        return f"{sign}${magnitude:,.{digits}f}"
    digits = decimals if decimals is not None else 0
    if compact and abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    if compact and abs(number) >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{number:,.{digits}f}"


def period_delta_text(current, previous) -> tuple[str, str]:
    """Return (delta_text, direction) where direction is "up" | "down" | "flat" for period
    comparisons, matching ui/components.py::period_delta's truthful-baseline behavior."""
    if current is None or previous is None or pd.isna(current) or pd.isna(previous):
        return "No prior baseline", "flat"
    if abs(float(previous)) < 1e-12:
        return "No prior baseline", "flat"
    change = (float(current) - float(previous)) / abs(float(previous))
    direction = "up" if change > 0 else "down" if change < 0 else "flat"
    return f"{change:+.1%} vs prior period", direction
