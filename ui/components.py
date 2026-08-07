from __future__ import annotations

import math
import re

import pandas as pd
import streamlit as st

from ui.kpi_governance import kpi_help


def balanced_row_sizes(count: int, max_per_row: int = 4) -> list[int]:
    """Split `count` items into rows of at most `max_per_row`, sized as evenly as possible —
    5 items become 3+2 rather than 4+1, so a row never ends with one card stretched full-width."""
    if count <= max_per_row:
        return [count] if count else []
    rows = math.ceil(count / max_per_row)
    base, extra = divmod(count, rows)
    return [base + 1 if index < extra else base for index in range(rows)]


def kpis(items: list[tuple[str, str, str | None]], ctx, columns: int | None = None) -> None:
    start = 0
    for size in balanced_row_sizes(len(items), max(1, columns or 4)):
        row = items[start:start + size]
        start += size
        cols = st.columns(len(row), gap="medium")
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
        return "—"
    sign = "-" if value < 0 else ""
    value = abs(value)
    if compact and value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.2f}M"
    if compact and value >= 1_000:
        return f"{sign}${value / 1_000:.1f}K"
    return f"{sign}${value:,.0f}"


def pct(value: float, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value * 100:.{digits}f}%"


def number(value: float, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "—"
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
