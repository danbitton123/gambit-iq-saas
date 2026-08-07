from __future__ import annotations

import plotly.graph_objects as go

from ui.charts import polish


def test_polish_never_leaves_an_undefined_figure_title():
    """A figure with only a trace-level title (e.g. go.Indicator gauges) has no
    layout.title.text; Streamlit's chart accessibility caption reads that property and
    renders the literal text "undefined" when it's unset. polish() must always set it."""
    fig = go.Figure(go.Indicator(mode="gauge+number", value=50, title={"text": "Churn risk"}))
    assert fig.layout.title.text is None
    polished = polish(fig)
    assert polished.layout.title.text is not None


def test_polish_preserves_an_explicit_title():
    fig = go.Figure(go.Bar(x=[1, 2], y=[3, 4]))
    fig.update_layout(title="REVENUE TREND")
    polished = polish(fig)
    assert polished.layout.title.text == "REVENUE TREND"
