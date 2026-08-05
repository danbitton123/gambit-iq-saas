from __future__ import annotations

import math
import re

import pandas as pd
import streamlit as st

from ui.kpi_governance import kpi_help


def kpis(items: list[tuple[str, str, str | None]], ctx, columns: int | None = None) -> None:
    per_row = max(1, columns or len(items))
    for start in range(0, len(items), per_row):
        row = items[start:start + per_row]
        cols = st.columns(len(row))
        for col, (label, value, delta) in zip(cols, row):
            is_comparison = bool(delta and re.match(r"^[+\-−]?\d", str(delta)))
            col.metric(
                label,
                value,
                delta,
                delta_color="normal" if is_comparison else "off",
                help=kpi_help(label, ctx.period_label, ctx.last_updated_label()),
            )


def insight(title: str, body: str, impact: str = "", risk: bool = False) -> None:
    cls = "risk" if risk else "impact"
    st.markdown(
        f"<div class='insight-card'><strong>{title}</strong><br><small>{body}</small>"
        f"<div class='{cls}' style='margin-top:7px'>{impact}</div></div>",
        unsafe_allow_html=True,
    )


def money(value: float, compact: bool = True) -> str:
    if value is None or pd.isna(value):
        return "Missing data"
    sign = "-" if value < 0 else ""
    value = abs(value)
    if compact and value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.2f}M"
    if compact and value >= 1_000:
        return f"{sign}${value / 1_000:.1f}K"
    return f"{sign}${value:,.0f}"


def pct(value: float, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "Missing data"
    return f"{value * 100:.{digits}f}%"


def number(value: float, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "Missing data"
    return f"{value:,.{digits}f}"


def period_delta(current: float, previous: float, digits: int = 1) -> str:
    """Return a truthful period-over-period change for Streamlit metrics."""
    if current is None or previous is None or pd.isna(current) or pd.isna(previous):
        return "No prior baseline"
    if math.isclose(float(previous), 0.0, abs_tol=1e-12):
        return "No prior baseline"
    change = (float(current) - float(previous)) / abs(float(previous))
    return f"{change:+.{digits}%} vs prior period"


def empty_state(title: str = "No data for these filters") -> None:
    st.info(f"{title}. Try a wider date range or another market.", icon="ℹ️")


def chart(fig, data=None, *, explanation: str = "", height: int | None = None) -> None:
    """Render a chart consistently and replace empty charts with a useful state."""
    if data is not None and hasattr(data, "empty") and data.empty:
        empty_state()
        return
    if height is not None:
        fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "responsive": True})
    if explanation:
        st.caption(explanation)


def data_table(df: pd.DataFrame, *, column_config: dict | None = None, empty_title: str = "No rows match these filters") -> None:
    if df.empty:
        empty_state(empty_title)
        return
    st.dataframe(df, width="stretch", hide_index=True, column_config=column_config or {})
