from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from ui.charts import polish
from ui.components import chart, money, pct, period_delta
from ui.kpi_governance import kpi_help
from ui.theme import page_header


COST_SQL = "CASE p.channel WHEN 'Google' THEN 34 WHEN 'Meta' THEN 38 WHEN 'Organic' THEN 8 WHEN 'Affiliate Alpha' THEN 47 WHEN 'Affiliate Nova' THEN 61 WHEN 'Influencers' THEN 73 ELSE 40 END"


def _num(value, default: float = 0.0) -> float:
    return default if value is None or pd.isna(value) else float(value)


def _change(current: float, previous: float) -> float | None:
    return None if math.isclose(previous, 0.0, abs_tol=1e-12) else (current - previous) / abs(previous)


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


def _forecast_card(label: str, value: str, note: str, tone: str = "neutral") -> None:
    st.markdown(
        f"<div class='forecast-card forecast-{tone}'><span>{label}</span>"
        f"<strong>{value}</strong><small>{note}</small></div>", unsafe_allow_html=True
    )


def _recommendation(title: str, what: str, why: str, impact: str, action: str, confidence: float) -> None:
    level = "High" if confidence >= .8 else "Medium" if confidence >= .65 else "Low"
    st.markdown(
        f"<article class='recommendation-card'><div class='recommendation-head'><strong>{title}</strong>"
        f"<span>{level} confidence · {confidence:.0%}</span></div>"
        f"<div class='recommendation-grid'><div><small>WHAT IS HAPPENING?</small><p>{what}</p></div>"
        f"<div><small>WHY?</small><p>{why}</p></div><div><small>ESTIMATED IMPACT</small><p>{impact}</p></div>"
        f"<div><small>RECOMMENDED ACTION</small><p>{action}</p></div></div></article>",
        unsafe_allow_html=True,
    )


def render(ctx) -> None:
    page_header("COMMAND CENTER", "Performance, priorities, forecasts and decisions in one governed view", "Executive Intelligence")

    metric_sql = """
      WITH gaming AS (
        SELECT COALESCE(SUM(total_ggr),0) ggr,COALESCE(SUM(estimated_ngr),0) ngr,
               COALESCE(SUM(total_wagers),0) wagers,
               COALESCE(SUM(casino_payouts+sports_payout),0) payouts
        FROM mart_executive_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
          AND (:country='All markets' OR country=:country)
      ), active AS (
        SELECT COUNT(DISTINCT a.player_id) players FROM int_player_activity_daily a
        JOIN dim_player p USING(player_id) WHERE activity_date>=DATE(:start) AND activity_date<DATE(:end)
          AND (:country='All markets' OR p.country=:country)
      ), payments AS (
        SELECT COALESCE(SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Deposit' THEN amount ELSE 0 END),0) deposits
        FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end
          AND (:country='All markets' OR country=:country)
      ), first_deposit AS (
        SELECT player_id,MIN(transaction_date) ftd_date FROM transactions
        WHERE transaction_type='Deposit' AND transaction_status='Approved' GROUP BY player_id
      ), ftd AS (
        SELECT COUNT(*) value FROM first_deposit f JOIN players p USING(player_id)
        WHERE ftd_date>=:start AND ftd_date<:end AND (:country='All markets' OR p.country=:country)
      ) SELECT gaming.*,active.players,payments.deposits,ftd.value ftd FROM gaming,active,payments,ftd
    """
    current = ctx.query(metric_sql).iloc[0]
    previous = ctx.previous_query(metric_sql).iloc[0]
    days = max((ctx.end.normalize() - ctx.start.normalize()).days + 1, 1)

    targets = {
        "ggr": _num(previous.ggr) * 1.05 if _num(previous.ggr) > 0 else max(_num(current.ggr), 1),
        "ngr": _num(previous.ngr) * 1.05 if _num(previous.ngr) > 0 else max(_num(current.ngr), 1),
        "players": _num(previous.players) * 1.03 if _num(previous.players) > 0 else max(_num(current.players), 1),
        "deposits": _num(previous.deposits) * 1.05 if _num(previous.deposits) > 0 else max(_num(current.deposits), 1),
        "ftd": _num(previous.ftd) * 1.05 if _num(previous.ftd) > 0 else max(_num(current.ftd), 1),
        "hold": .07,
    }
    hold = _num(current.ggr) / _num(current.wagers) if _num(current.wagers) else 0
    previous_hold = _num(previous.ggr) / _num(previous.wagers) if _num(previous.wagers) else 0

    st.markdown("### Performance at a glance")
    st.caption("Observed results, period-over-period movement and management objectives. Objectives use the prior period +5% (+3% for active players); blended hold objective is 7%.")
    _executive_kpis([
        {"label": "Observed Total GGR", "value": money(current.ggr), "delta": period_delta(current.ggr, previous.ggr), "progress": _num(current.ggr)/targets["ggr"], "objective": money(targets["ggr"])},
        {"label": "Estimated NGR", "value": money(current.ngr), "delta": period_delta(current.ngr, previous.ngr), "progress": _num(current.ngr)/targets["ngr"], "objective": money(targets["ngr"])},
        {"label": "Observed Active Players", "value": f"{int(current.players or 0):,}", "delta": period_delta(current.players, previous.players), "progress": _num(current.players)/targets["players"], "objective": f"{targets['players']:,.0f}"},
        {"label": "Observed Deposits", "value": money(current.deposits), "delta": period_delta(current.deposits, previous.deposits), "progress": _num(current.deposits)/targets["deposits"], "objective": money(targets["deposits"])},
        {"label": "Observed FTD", "value": f"{int(current.ftd or 0):,}", "delta": period_delta(current.ftd, previous.ftd), "progress": _num(current.ftd)/targets["ftd"], "objective": f"{targets['ftd']:,.0f}"},
        {"label": "Observed Blended Hold", "value": pct(hold, 2), "delta": period_delta(hold, previous_hold), "progress": hold/targets["hold"], "objective": "7.0% hold"},
    ], ctx)

    active_condition = """(:country='All markets' OR v.country=:country) AND EXISTS (
      SELECT 1 FROM int_player_activity_daily a WHERE a.player_id=v.player_id
      AND a.activity_date>=DATE(:start) AND a.activity_date<DATE(:end))"""
    risk_sql = f"""SELECT COUNT(*) scored,AVG(churn_probability) churn_rate,
      SUM(churn_probability>=.70) high_churn,SUM(CASE WHEN churn_probability>=.70 THEN predicted_ltv_90d ELSE 0 END) value_at_risk,
      SUM(predicted_ltv_90d) future_ltv,AVG(model_confidence) confidence,
      SUM(fraud_risk>=.55) payment_risk FROM v_player_scores v WHERE {active_condition}"""
    risk_now = ctx.query(risk_sql).iloc[0]
    risk_previous = ctx.previous_query(risk_sql).iloc[0]
    churn_change = (_num(risk_now.churn_rate) - _num(risk_previous.churn_rate))

    game = ctx.query("""SELECT game_name,SUM(payouts)/NULLIF(SUM(bets),0) actual_rtp,
      AVG(theoretical_rtp) theoretical_rtp,SUM(payouts)/NULLIF(SUM(bets),0)-AVG(theoretical_rtp) variance,SUM(bets) bets
      FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
      AND (:country='All markets' OR country=:country) GROUP BY game_name HAVING SUM(bets)>0
      ORDER BY ABS(variance) DESC LIMIT 1""")
    game_row = game.iloc[0] if not game.empty else None
    rtp_variance = abs(_num(game_row.variance)) if game_row is not None else 0

    campaign = ctx.query(f"""SELECT p.channel,COUNT(*) players,SUM({COST_SQL}) cost,
      SUM(v.predicted_ltv_90d) predicted_value,SUM(v.predicted_ltv_90d)/NULLIF(SUM({COST_SQL}),0) roas
      FROM players p JOIN v_player_scores v USING(player_id)
      WHERE p.registration_date>=:start AND p.registration_date<:end
      AND (:country='All markets' OR p.country=:country) GROUP BY p.channel ORDER BY roas LIMIT 1""")
    campaign_row = campaign.iloc[0] if not campaign.empty else None
    worst_roas = _num(campaign_row.roas) if campaign_row is not None else 0

    payment_sql = """SELECT AVG(transaction_status='Approved') approval FROM v_transactions_enriched
      WHERE transaction_date>=:start AND transaction_date<:end AND transaction_type='Deposit'
      AND (:country='All markets' OR country=:country)"""
    payment = ctx.query(payment_sql).iloc[0]
    previous_payment = ctx.previous_query(payment_sql).iloc[0]
    approval_drop = max(_num(previous_payment.approval) - _num(payment.approval), 0)

    sportsbook = ctx.query("""WITH events AS (SELECT event_name,SUM(stake) handle FROM v_sports_bets_enriched
      WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY event_name)
      SELECT event_name,handle,handle/(SELECT NULLIF(SUM(handle),0) FROM events) share FROM events ORDER BY handle DESC LIMIT 1""")
    sportsbook_row = sportsbook.iloc[0] if not sportsbook.empty else None
    event_share = _num(sportsbook_row.share) if sportsbook_row is not None else 0
    revenue_change = _change(_num(current.ggr), _num(previous.ggr)) or 0

    st.markdown("### Action required")
    alert_cols = st.columns(3)
    alerts = [
        ("Revenue momentum", "GGR versus the immediately preceding equivalent period.", f"{revenue_change:+.1%}", _severity(max(-revenue_change, 0), .05, .12), "Review the revenue mix and largest negative contributors."),
        ("Casino RTP anomaly", f"{game_row.game_name if game_row is not None else 'No game'} has the largest absolute variance from theoretical RTP.", f"{rtp_variance:+.2%} abs. variance", _severity(rtp_variance, .02, .04), "Validate sample size, game configuration and provider feed."),
        ("Acquisition efficiency", f"{campaign_row.channel if campaign_row is not None else 'No channel'} is the weakest predicted 90-day ROAS proxy.", f"{worst_roas:.2f}x ROAS proxy", "critical" if worst_roas and worst_roas < 1 else "warning" if worst_roas < 2 else "stable", "Review spend assumptions before reallocating budget."),
        ("Predicted churn", "Average churn probability among players active in the selected scope.", f"{churn_change:+.1%} vs prior", _severity(max(churn_change, 0), .03, .08), f"Prioritize {int(risk_now.high_churn or 0):,} high-risk players."),
        ("Payment risk", "Change in observed deposit approval rate versus the previous period.", f"{approval_drop:.1%} approval decline", _severity(approval_drop, .02, .05), "Inspect declines by payment method and issuer."),
        ("Sportsbook concentration", f"{sportsbook_row.event_name if sportsbook_row is not None else 'No event'} holds the largest share of settled handle.", f"{event_share:.1%} of handle", _severity(event_share, .30, .45), "Review event-level concentration and trading limits."),
    ]
    for index, args in enumerate(alerts):
        with alert_cols[index % 3]:
            _alert_card(*args)

    daily = ctx.query("""SELECT metric_date date,SUM(total_ggr) ggr FROM mart_executive_daily
      WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
      AND (:country='All markets' OR country=:country) GROUP BY metric_date ORDER BY metric_date""")
    daily["date"] = pd.to_datetime(daily.date)
    forecast = ctx.query("""SELECT forecast_date date,predicted_revenue forecast,lower_bound lower,upper_bound upper
      FROM revenue_forecast ORDER BY forecast_date""")
    forecast["date"] = pd.to_datetime(forecast.date)
    market_share = 1.0
    if ctx.country != "All markets":
        total_recent = ctx.repo.scalar("SELECT SUM(total_ggr) FROM mart_executive_daily WHERE metric_date>=(SELECT DATE(MAX(metric_date),'-29 days') FROM mart_executive_daily)") or 0
        market_recent = ctx.repo.scalar("SELECT SUM(total_ggr) FROM mart_executive_daily WHERE country=:country AND metric_date>=(SELECT DATE(MAX(metric_date),'-29 days') FROM mart_executive_daily)", {"country": ctx.country}) or 0
        market_share = max(float(market_recent) / float(total_recent), 0) if total_recent else 0
        forecast[["forecast", "lower", "upper"]] *= market_share
    forecast_7 = forecast.head(7).forecast.sum()
    forecast_30 = forecast.head(30).forecast.sum()
    run_rate_target_30 = max(_num(current.ggr) / days * 30 * 1.05, 0)
    forecast_gap = forecast_30 - run_rate_target_30
    revenue_at_risk = _num(risk_now.value_at_risk)
    future_ltv = _num(risk_now.future_ltv)

    st.markdown("### Forward outlook")
    forecast_cols = st.columns(5)
    forecast_items = [
        ("Predicted GGR · 7 days", money(forecast_7), "Revenue forecast model", "positive"),
        ("Predicted GGR · 30 days", money(forecast_30), "Market-share adjusted" if ctx.country != "All markets" else "All-market model", "positive"),
        ("Predicted high churn", f"{int(risk_now.high_churn or 0):,}", f"{pct(risk_now.churn_rate)} average probability", "risk"),
        ("Predicted LTV Proxy · 90D", money(future_ltv), "Active players in scope", "neutral"),
        ("Forecast gap to target", money(forecast_gap), f"Target {money(run_rate_target_30)}", "positive" if forecast_gap >= 0 else "risk"),
    ]
    for col, item in zip(forecast_cols, forecast_items):
        with col:
            _forecast_card(*item)

    left, right = st.columns([1.65, 1])
    with left:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily.date, y=daily.ggr, name="Observed GGR", line=dict(color=COLORS["cyan"], width=2.5)))
        fig.add_trace(go.Scatter(x=forecast.date, y=forecast.upper, line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=forecast.date, y=forecast.lower, fill="tonexty", fillcolor="rgba(38,198,229,.13)", line=dict(width=0), name="Prediction interval"))
        fig.add_trace(go.Scatter(x=forecast.date, y=forecast.forecast, name="Predicted GGR", line=dict(color=COLORS["gold"], width=2.5, dash="dot")))
        fig.add_hline(y=run_rate_target_30/30 if run_rate_target_30 else 0, line_dash="dash", line_color=COLORS["green"], annotation_text="Daily objective")
        fig.update_layout(title="OBSERVED PERFORMANCE & 30-DAY FORECAST")
        chart(polish(fig, 390), explanation="Observed filtered GGR followed by the model forecast and prediction interval. Country views use the market's recent observed GGR share.")
    with right:
        risk_bands = ctx.query(f"""SELECT CASE WHEN churn_probability<.40 THEN 'Stable' WHEN churn_probability<.70 THEN 'Watch' ELSE 'High risk' END segment,
          COUNT(*) players,SUM(predicted_ltv_90d) ltv_proxy,AVG(model_confidence) confidence FROM v_player_scores v
          WHERE {active_condition} GROUP BY segment""")
        color_map = {"Stable": COLORS["green"], "Watch": COLORS["gold"], "High risk": COLORS["red"]}
        fig = px.bar(risk_bands, x="segment", y="ltv_proxy", color="segment", text="players", title="LTV PROXY AT RISK BY CHURN BAND", color_discrete_map=color_map)
        fig.update_traces(texttemplate="%{text:,} players", textposition="outside")
        chart(polish(fig, 390, False), risk_bands, explanation="Predicted 90-day LTV Proxy of active players, segmented by predicted churn probability.")

    st.markdown("### Recommended decisions")
    st.caption("Decision support only. Every recommendation explains the signal, cause, impact, action and model confidence; execution remains human-approved.")
    recommendation_cols = st.columns(2)
    recommendations = [
        ("Protect high-value players", f"Predicted churn risk is elevated for {int(risk_now.high_churn or 0):,} active players.", "The churn model detects lower recent activity and weaker engagement patterns.", f"Up to {money(revenue_at_risk)} of predicted 90-day LTV Proxy is attached to the high-risk group.", f"Launch a targeted retention journey for {int(risk_now.high_churn or 0):,} players, excluding fraud and RG flags.", _num(risk_now.confidence, .68)),
        ("Correct the largest RTP deviation", f"{game_row.game_name if game_row is not None else 'The leading game'} differs from theoretical RTP by {rtp_variance:.2%}.", "Observed payouts diverge from the configured theoretical return; sample size and feed quality may contribute.", f"{money(_num(game_row.bets) if game_row is not None else 0)} of observed bets require validation.", "Confirm game configuration, provider settlement data and statistical significance before escalation.", .88 if game_row is not None and _num(game_row.bets) > 10000 else .70),
        ("Improve acquisition allocation", f"{campaign_row.channel if campaign_row is not None else 'The weakest channel'} has the lowest predicted ROAS proxy at {worst_roas:.2f}x.", "Predicted 90-day LTV Proxy is low relative to the channel cost assumption.", f"Review {int(campaign_row.players if campaign_row is not None else 0):,} acquired players before the next budget cycle.", "Validate actual media spend, then reduce or redesign the weakest cohort while protecting high-quality sources.", _num(risk_now.confidence, .68)),
        ("Reduce operational exposure", f"Deposit approvals declined {approval_drop:.1%}; the largest sportsbook event represents {event_share:.1%} of handle.", "Payment friction and concentrated settled handle can increase liquidity and trading volatility.", f"Current approved deposits total {money(current.deposits)}; concentrated event handle is {money(sportsbook_row.handle if sportsbook_row is not None else 0)}.", "Review payment-method declines and event limits in parallel; escalate only breaches above approved thresholds.", .82),
    ]
    for index, args in enumerate(recommendations):
        with recommendation_cols[index % 2]:
            _recommendation(*args)
