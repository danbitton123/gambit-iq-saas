from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from config import COLORS


PALETTE = [COLORS["cyan"], COLORS["green"], COLORS["gold"], "#8b76ff", COLORS["red"], "#55a7ff"]


def polish(fig: go.Figure, height: int = 360, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=18, r=18, t=48, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["muted"], family="Inter"),
        title_font=dict(color=COLORS["text"], size=13, family="Manrope"),
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=10), title_text=""),
        showlegend=legend,
        hoverlabel=dict(bgcolor="#0a2730", font_color="#f4f7fb"),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="rgba(141,163,180,.15)")
    fig.update_yaxes(gridcolor=COLORS["grid"], zeroline=False)
    fig.update_layout(hovermode="closest", autosize=True)
    return fig


def line(df, x, y, color=None, title="", height=360):
    fig = px.line(df, x=x, y=y, color=color, title=title, color_discrete_sequence=PALETTE)
    fig.update_traces(line_width=2.4)
    return polish(fig, height)


def bars(df, x, y, color=None, title="", height=360, barmode="group"):
    fig = px.bar(df, x=x, y=y, color=color, title=title, barmode=barmode, color_discrete_sequence=PALETTE)
    return polish(fig, height)


def area_forecast(history, forecast, date_col="date", value_col="value", title="Revenue forecast"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history[date_col], y=history[value_col], name="Actual", line=dict(color=COLORS["cyan"], width=2.5)))
    fig.add_trace(go.Scatter(x=forecast[date_col], y=forecast["upper"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=forecast[date_col], y=forecast["lower"], fill="tonexty", fillcolor="rgba(38,198,229,.14)", line=dict(width=0), name="95% interval", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=forecast[date_col], y=forecast[value_col], name="Forecast", line=dict(color=COLORS["cyan"], width=2.5, dash="dot")))
    fig.update_layout(title=title)
    return polish(fig, 390)
