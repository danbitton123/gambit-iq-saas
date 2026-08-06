from __future__ import annotations

import plotly.express as px
import streamlit as st

from config import COLORS
from data.decision_engine import DecisionEngine
from pages.overview_metrics import load, num
from ui.charts import polish
from ui.components import chart, money, pct, period_delta
from ui.kpi_governance import kpi_help
from ui.theme import page_header


SEVERITY_RANK = {"Critical": 0, "High": 1, "Medium": 2}
TOP_ALERTS = 6


def _executive_kpis(items: list[dict], ctx) -> None:
    cols = st.columns(len(items))
    for index, item in enumerate(items):
        with cols[index]:
            st.metric(
                item["label"], item["value"], item["delta"],
                delta_color=item.get("delta_color", "normal"),
                help=kpi_help(item["label"], ctx.period_label, ctx.last_updated_label()),
            )
            progress = min(max(float(item["progress"]), 0.0), 1.0)
            st.progress(progress)
            st.caption(f"{progress:.0%} of objective · {item['objective']}")


def _alert_card(alert) -> None:
    css_severity = "critical" if alert.severity == "Critical" else "warning"
    st.markdown(
        f"<article class='command-alert command-alert-{css_severity}'>"
        f"<div class='command-alert-top'><span>{alert.severity.upper()} · {alert.market}</span><strong>{alert.title}</strong></div>"
        f"<div class='command-alert-value'>{alert.current_value}</div>"
        f"<p>{alert.kpi} · usual {alert.usual_value}. {alert.probable_cause}</p><small>{alert.recommendation}</small></article>",
        unsafe_allow_html=True,
    )


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

    with st.spinner("Evaluating governed decision rules…"):
        alerts = DecisionEngine(ctx).evaluate()
    # One card per distinct rule (its worst-affected market), not one per market — otherwise a
    # single rule triggering in every country would crowd out every other signal when "All
    # markets" is selected.
    worst_per_rule = {}
    for alert in alerts:
        current_worst = worst_per_rule.get(alert.rule_id)
        rank = (SEVERITY_RANK.get(alert.severity, 3), -alert.financial_impact)
        if current_worst is None or rank < (SEVERITY_RANK.get(current_worst.severity, 3), -current_worst.financial_impact):
            worst_per_rule[alert.rule_id] = alert
    top_alerts = sorted(worst_per_rule.values(), key=lambda alert: (SEVERITY_RANK.get(alert.severity, 3), -alert.financial_impact))[:TOP_ALERTS]

    st.markdown("### Action required")
    if not top_alerts:
        st.success("No governed rule is currently triggered for this period and market.")
    else:
        st.caption(f"The {len(top_alerts)} highest-severity distinct signals from the governed Decision Engine. Open AI Copilot → Intelligent alerts for the full register with status tracking.")
        alert_cols = st.columns(3)
        for index, alert in enumerate(top_alerts):
            with alert_cols[index % 3]:
                _alert_card(alert)

    st.markdown("### Risk concentration")
    color_map = {"Stable": COLORS["green"], "Watch": COLORS["gold"], "High risk": COLORS["red"]}
    fig = px.bar(metrics.bands, x="segment", y="ltv_proxy", color="segment", text="players", title="LTV PROXY AT RISK BY CHURN BAND", color_discrete_map=color_map)
    fig.update_traces(texttemplate="%{text:,} players", textposition="outside")
    chart(polish(fig, 390, False), metrics.bands, explanation="Predicted 90-day LTV Proxy of active players, segmented by predicted churn probability.")
