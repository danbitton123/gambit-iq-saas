from __future__ import annotations

import plotly.express as px
import streamlit as st

from config import COLORS
from pages.overview_metrics import load, num
from ui.charts import polish
from ui.components import chart, money, pct, period_delta
from ui.kpi_governance import kpi_help
from ui.theme import page_header


def _severity(value: float, warning: float, critical: float) -> str:
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "stable"


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


def _alert_card(title: str, detail: str, value: str, severity: str, action: str) -> None:
    labels = {"critical": "CRITICAL", "warning": "REVIEW", "stable": "STABLE"}
    st.markdown(
        f"<article class='command-alert command-alert-{severity}'>"
        f"<div class='command-alert-top'><span>{labels[severity]}</span><strong>{title}</strong></div>"
        f"<div class='command-alert-value'>{value}</div><p>{detail}</p><small>{action}</small></article>",
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

    game_row, campaign_row, sportsbook_row = metrics.game_row, metrics.campaign_row, metrics.sportsbook_row
    st.markdown("### Action required")
    st.caption("Six governed risk signals, refreshed for the selected period and market. See the Forecast & Recommendations page for the forward outlook and next actions.")
    alert_cols = st.columns(3)
    alerts = [
        ("Revenue momentum", "GGR versus the immediately preceding equivalent period.", f"{metrics.revenue_change:+.1%}", _severity(max(-metrics.revenue_change, 0), .05, .12), "Review the revenue mix and largest negative contributors."),
        ("Casino RTP anomaly", f"{game_row.game_name if game_row is not None else 'No game'} has the largest absolute variance from theoretical RTP.", f"{metrics.rtp_variance:+.2%} abs. variance", _severity(metrics.rtp_variance, .02, .04), "Validate sample size, game configuration and provider feed."),
        ("Acquisition efficiency", f"{campaign_row.channel if campaign_row is not None else 'No channel'} is the weakest predicted 90-day ROAS proxy.", f"{metrics.worst_roas:.2f}x ROAS proxy", "critical" if metrics.worst_roas and metrics.worst_roas < 1 else "warning" if metrics.worst_roas < 2 else "stable", "Review spend assumptions before reallocating budget."),
        ("Predicted churn", "Average churn probability among players active in the selected scope.", f"{metrics.churn_change:+.1%} vs prior", _severity(max(metrics.churn_change, 0), .03, .08), f"Prioritize {int(metrics.risk_now.high_churn or 0):,} high-risk players."),
        ("Payment risk", "Change in observed deposit approval rate versus the previous period.", f"{metrics.approval_drop:.1%} approval decline", _severity(metrics.approval_drop, .02, .05), "Inspect declines by payment method and issuer."),
        ("Sportsbook concentration", f"{sportsbook_row.event_name if sportsbook_row is not None else 'No event'} holds the largest share of settled handle.", f"{metrics.event_share:.1%} of handle", _severity(metrics.event_share, .30, .45), "Review event-level concentration and trading limits."),
    ]
    for index, args in enumerate(alerts):
        with alert_cols[index % 3]:
            _alert_card(*args)

    st.markdown("### Risk concentration")
    color_map = {"Stable": COLORS["green"], "Watch": COLORS["gold"], "High risk": COLORS["red"]}
    fig = px.bar(metrics.bands, x="segment", y="ltv_proxy", color="segment", text="players", title="LTV PROXY AT RISK BY CHURN BAND", color_discrete_map=color_map)
    fig.update_traces(texttemplate="%{text:,} players", textposition="outside")
    chart(polish(fig, 390, False), metrics.bands, explanation="Predicted 90-day LTV Proxy of active players, segmented by predicted churn probability.")
