from __future__ import annotations

import plotly.express as px
import streamlit as st

from config import COLORS
from data.decision_engine import DecisionEngine, top_alerts
from pages.overview_metrics import load, num
from ui.charts import polish
from ui.components import alert_card, balanced_row_sizes, chart, money, pct, period_delta
from ui.kpi_governance import kpi_help
from ui.theme import page_header


TOP_ALERTS = 6


def _executive_kpis(items: list[dict], ctx) -> None:
    start = 0
    for size in balanced_row_sizes(len(items), max_per_row=3):
        row = items[start:start + size]
        start += size
        cols = st.columns(len(row), gap="medium")
        for col, item in zip(cols, row):
            with col:
                st.metric(
                    item["label"], item["value"], item["delta"],
                    delta_color=item.get("delta_color", "normal"),
                    help=kpi_help(item["label"], ctx.period_label, ctx.last_updated_label()),
                )
                progress = min(max(float(item["progress"]), 0.0), 1.0)
                st.progress(progress)
                st.caption(f"{progress:.0%} of objective · {item['objective']}")


def render(ctx) -> None:
    page_header("COMMAND CENTER", "Real-time performance and priorities in one governed view", "Executive Intelligence")

    metrics = load(ctx)
    current, previous = metrics.current, metrics.previous

    targets = {
        "ggr": num(previous.ggr) * 1.05 if num(previous.ggr) > 0 else max(num(current.ggr), 1),
        "ngr": num(previous.ngr) * 1.05 if num(previous.ngr) > 0 else max(num(current.ngr), 1),
        "players": num(previous.players) * 1.03 if num(previous.players) > 0 else max(num(current.players), 1),
        "deposits": num(previous.deposits) * 1.05 if num(previous.deposits) > 0 else max(num(current.deposits), 1),
        "ftd": num(previous.ftd) * 1.05 if num(previous.ftd) > 0 else max(num(current.ftd), 1),
        "hold": .07,
    }

    st.markdown("### Performance at a glance")
    st.caption("Observed results, period-over-period movement and management objectives. Objectives use the prior period +5% (+3% for active players); blended hold objective is 7%.")
    _executive_kpis([
        {"label": "Observed Total GGR", "value": money(current.ggr), "delta": period_delta(current.ggr, previous.ggr), "progress": num(current.ggr)/targets["ggr"], "objective": money(targets["ggr"])},
        {"label": "Estimated NGR", "value": money(current.ngr), "delta": period_delta(current.ngr, previous.ngr), "progress": num(current.ngr)/targets["ngr"], "objective": money(targets["ngr"])},
        {"label": "Observed Active Players", "value": f"{int(current.players or 0):,}", "delta": period_delta(current.players, previous.players), "progress": num(current.players)/targets["players"], "objective": f"{targets['players']:,.0f}"},
        {"label": "Observed Deposits", "value": money(current.deposits), "delta": period_delta(current.deposits, previous.deposits), "progress": num(current.deposits)/targets["deposits"], "objective": money(targets["deposits"])},
        {"label": "Observed FTD", "value": f"{int(current.ftd or 0):,}", "delta": period_delta(current.ftd, previous.ftd), "progress": num(current.ftd)/targets["ftd"], "objective": f"{targets['ftd']:,.0f}"},
        {"label": "Observed Blended Hold", "value": pct(metrics.hold, 2), "delta": period_delta(metrics.hold, metrics.previous_hold), "progress": metrics.hold/targets["hold"], "objective": "7.0% hold"},
    ], ctx)

    st.markdown("### Revenue trend")
    fig = px.line(metrics.daily, x="date", y="ggr", title="TOTAL GGR · DAILY")
    fig.update_traces(line_color=COLORS["cyan"], line_width=2.4)
    chart(polish(fig, 300), metrics.daily, explanation="Observed casino and sportsbook GGR for every day in the selected period and market.")

    with st.spinner("Evaluating governed decision rules…"):
        alerts = DecisionEngine(ctx).evaluate()
    top = top_alerts(alerts, limit=TOP_ALERTS)

    st.markdown("### Action required")
    if not top:
        st.success("No governed rule is currently triggered for this period and market.")
    else:
        st.caption(f"The {len(top)} highest-severity distinct signals from the governed Decision Engine, across every team, ranked most severe first. Open AI Copilot → Intelligent alerts for the full register with status tracking.")
        start = 0
        for size in balanced_row_sizes(len(top), max_per_row=3):
            row = top[start:start + size]
            start += size
            for col, alert in zip(st.columns(len(row), gap="medium"), row):
                with col:
                    alert_card(alert)

    st.markdown("### Risk concentration")
    color_map = {"Stable": COLORS["green"], "Watch": COLORS["gold"], "High risk": COLORS["red"]}
    fig = px.bar(metrics.bands, x="segment", y="ltv_proxy", color="segment", text="players", title="LTV PROXY AT RISK BY CHURN BAND", color_discrete_map=color_map)
    fig.update_traces(texttemplate="%{text:,} players", textposition="outside")
    chart(polish(fig, 390, False), metrics.bands, explanation="Predicted 90-day LTV Proxy of active players, segmented by predicted churn probability.")
