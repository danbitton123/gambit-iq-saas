from __future__ import annotations

import streamlit as st


def kpis(items: list[tuple[str, str, str | None]], columns: int | None = None) -> None:
    cols = st.columns(columns or len(items))
    for col, (label, value, delta) in zip(cols, items):
        col.metric(label, value, delta)


def insight(title: str, body: str, impact: str = "", risk: bool = False) -> None:
    cls = "risk" if risk else "impact"
    st.markdown(
        f"<div class='insight-card'><strong>{title}</strong><br><small>{body}</small>"
        f"<div class='{cls}' style='margin-top:7px'>{impact}</div></div>",
        unsafe_allow_html=True,
    )


def money(value: float, compact: bool = True) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    if compact and value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.2f}M"
    if compact and value >= 1_000:
        return f"{sign}${value / 1_000:.1f}K"
    return f"{sign}${value:,.0f}"


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"

