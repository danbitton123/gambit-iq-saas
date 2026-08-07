from __future__ import annotations

"""Renders a single Widget's content. Every widget type is wrapped in its own error boundary —
one broken widget (bad config, transient query failure) never takes out the rest of the
dashboard or the page around it."""

import logging

import plotly.express as px
import streamlit as st

from dashboard_builder.formatting import format_value, infer_format, period_delta_text
from dashboard_builder.models import Widget
from dashboard_builder.query_engine import WidgetDataError, run_kpi_query, run_widget_query
from dashboard_builder.validation import validate_widget
from ui.charts import PALETTE, polish
from ui.components import data_table

LOGGER = logging.getLogger(__name__)
CHART_HEIGHT = 260


def render_widget_content(ctx, widget: Widget, dashboard=None) -> None:
    reason = validate_widget(widget)
    if reason:
        st.caption(reason)
        return
    try:
        if widget.type == "text":
            _render_text(widget)
        elif widget.type == "kpi":
            _render_kpi(ctx, widget, dashboard)
        elif widget.type == "table":
            _render_table(ctx, widget, dashboard)
        else:
            _render_chart(ctx, widget, dashboard)
    except WidgetDataError as exc:
        st.info(str(exc))
    except Exception:
        LOGGER.exception("Dashboard widget %s (%s) failed to render", widget.id, widget.type)
        st.info("This metric is not available for this casino, or the widget's configuration needs adjusting.")


def _render_text(widget: Widget) -> None:
    st.markdown(widget.text_content or "*Empty text block*")


def _render_kpi(ctx, widget: Widget, dashboard) -> None:
    current_value, previous_value, label = run_kpi_query(ctx, widget, dashboard)
    fmt = infer_format(label)
    value_text = format_value(current_value, fmt, compact=widget.compact_numbers)
    delta_text, direction = period_delta_text(current_value, previous_value) if widget.comparison == "previous_period" else ("", "flat")
    st.metric(widget.title if widget.show_title else label, value_text, delta_text or None, delta_color="normal" if direction != "flat" else "off")


def _render_table(ctx, widget: Widget, dashboard) -> None:
    result = run_widget_query(ctx, widget, dashboard)
    frame = result.frame
    if frame.empty:
        st.caption("No data available for the selected period.")
        return
    column_config = {}
    for measure_label in result.measure_labels:
        fmt = infer_format(measure_label)
        if fmt == "currency":
            column_config[measure_label] = st.column_config.NumberColumn(measure_label, format="$%.0f")
        elif fmt == "percent":
            column_config[measure_label] = st.column_config.NumberColumn(measure_label, format="%.1%%")
    data_table(frame, column_config=column_config)
    st.download_button(
        "Export CSV", frame.to_csv(index=False).encode("utf-8"), file_name=f"casino_ai_{widget.id}.csv",
        mime="text/csv", key=f"export_{widget.id}", width="stretch",
    )


def _render_chart(ctx, widget: Widget, dashboard) -> None:
    result = run_widget_query(ctx, widget, dashboard)
    frame = result.frame
    if frame.empty:
        st.caption("No data available for the selected period.")
        return
    dim_col = result.dimension_label
    measure_cols = result.measure_labels
    colors = [widget.accent_color] + PALETTE if widget.accent_color else PALETTE
    title = widget.title.upper() if widget.show_title else ""

    if widget.type == "line":
        fig = px.line(frame, x=dim_col, y=measure_cols, title=title, color_discrete_sequence=colors, markers=len(frame) <= 60)
    elif widget.type == "bar":
        fig = px.bar(frame, x=dim_col, y=measure_cols, title=title, color_discrete_sequence=colors, barmode="group")
    elif widget.type == "pie":
        fig = px.pie(frame, names=dim_col, values=measure_cols[0], title=title, color_discrete_sequence=colors, hole=0.45)
    elif widget.type == "scatter":
        fig = px.scatter(
            frame, x=measure_cols[0], y=measure_cols[1], color=dim_col if dim_col else None,
            title=title, color_discrete_sequence=colors,
        )
    else:
        st.caption("Unsupported chart type.")
        return
    fig.update_layout(margin=dict(t=36 if title else 10))
    st.plotly_chart(polish(fig, CHART_HEIGHT, legend=len(measure_cols) > 1 or bool(dim_col and widget.type in ("pie", "scatter"))), width="stretch", config={"displayModeBar": False, "responsive": True}, key=f"chart_{widget.id}")
    with st.expander("View data", expanded=False):
        data_table(frame)
