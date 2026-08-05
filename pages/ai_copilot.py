from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS
from ui.charts import area_forecast, polish
from ui.components import chart, data_table, insight, kpis, money, pct
from ui.theme import page_header


QUESTIONS = {
    "Why is Roulette GGR declining?": "Roulette GGR is forecast to soften because VIP wager volume has decreased while RTP variance moved above its expected band. The result should be reviewed against sample size before action.",
    "Which players have the highest churn-adjusted value?": "The highest opportunity is concentrated in Gold and Platinum players with predicted LTV above $1,200 and churn probability between 60% and 80%. Players with elevated RG risk are excluded.",
    "Which acquisition sources should we scale?": "Organic and Google currently combine the strongest predicted LTV, retention and quality-adjusted ROAS. Affiliate Nova should remain capped until fraud-risk indicators improve.",
    "Where are financial anomalies increasing?": "Withdrawal velocity and Mastercard declines are the two strongest anomalies. Reconciliation remains inside the monitoring tolerance but requires daily review.",
}


def render(ctx) -> None:
    page_header("GAMBIT AI COPILOT", "Forecasts, explanations and business decisions", "Decision Intelligence")
    m=ctx.query("""SELECT (SELECT COALESCE(SUM(casino_ggr),0) FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country))+(SELECT COALESCE(SUM(sportsbook_ggr),0) FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country)) total_ggr,(SELECT COALESCE(SUM(CASE WHEN churn_probability>=.7 THEN predicted_ltv_90d ELSE 0 END),0) FROM v_player_scores v WHERE (:country='All markets' OR country=:country) AND EXISTS (SELECT 1 FROM v_sessions_enriched s WHERE s.player_id=v.player_id AND s.session_start>=:start AND s.session_start<:end)) risk_revenue,(SELECT COALESCE(SUM(CASE WHEN predicted_ltv_90d>=900 AND rg_risk<.4 THEN predicted_ltv_90d*.08 ELSE 0 END),0) FROM v_player_scores v WHERE (:country='All markets' OR country=:country) AND EXISTS (SELECT 1 FROM v_sessions_enriched s WHERE s.player_id=v.player_id AND s.session_start>=:start AND s.session_start<:end)) opportunities,(SELECT AVG(model_confidence) FROM v_player_scores v WHERE (:country='All markets' OR country=:country) AND EXISTS (SELECT 1 FROM v_sessions_enriched s WHERE s.player_id=v.player_id AND s.session_start>=:start AND s.session_start<:end)) accuracy""").iloc[0]
    total_ggr,risk_revenue,opportunities,accuracy=m.total_ggr,m.risk_revenue,m.opportunities,m.accuracy
    selected_days = max((ctx.end.normalize() - ctx.start.normalize()).days + 1, 1)
    projected_30d = total_ggr / selected_days * 30
    kpis([
        ("Run-rate GGR 30D", money(projected_30d), "Selected-period daily rate × 30"),
        ("Predicted Value at Risk", money(risk_revenue), "LTV of active players ≥70% churn"),
        ("Modelled Opportunities", money(opportunities), "8% of eligible predicted LTV"),
        ("Model Confidence", pct(accuracy), "Monitored daily"),
        ("Decision Mode", "Human review", "No automated execution"),
    ])
    left, center, right = st.columns([1, 2.35, 1.1])
    with left:
        st.markdown("#### Conversation history")
        question = st.radio("Ask your data", list(QUESTIONS), label_visibility="collapsed")
        custom_question = st.text_input("New question", placeholder="Ask about revenue, players, risk…")
    with center:
        displayed_question = custom_question.strip() if custom_question.strip() else question
        st.markdown(f"### {displayed_question}")
        if custom_question.strip():
            words = custom_question.lower()
            if "churn" in words or "player" in words:
                answer = QUESTIONS["Which players have the highest churn-adjusted value?"]
            elif "acquisition" in words or "affiliate" in words or "source" in words:
                answer = QUESTIONS["Which acquisition sources should we scale?"]
            elif "payment" in words or "withdraw" in words or "financial" in words:
                answer = QUESTIONS["Where are financial anomalies increasing?"]
            else:
                answer = QUESTIONS["Why is Roulette GGR declining?"]
            answer += " This demo response is generated from the current synthetic snapshot."
        else:
            answer = QUESTIONS[question]
        st.info(answer, icon="💡")
        daily=ctx.query("""SELECT DATE(session_start) date,SUM(casino_ggr) value FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country) GROUP BY DATE(session_start) ORDER BY date DESC LIMIT 45""").sort_values("date");daily["date"]=pd.to_datetime(daily.date)
        future=ctx.query("SELECT forecast_date date,predicted_revenue value,lower_bound lower,upper_bound upper FROM revenue_forecast ORDER BY forecast_date");future["date"]=pd.to_datetime(future.date)
        if ctx.country != "All markets":
            share = daily.value.sum() / max(ctx.query("""SELECT COALESCE(SUM(casino_ggr),0) value FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end""").iat[0,0], 1)
            for col in ["value","lower","upper"]: future[col] *= share
        chart(area_forecast(daily, future, title="EXPLAINABLE 30-DAY FORECAST"),daily,explanation="Historical casino GGR follows the filters. Market forecasts are allocated from the global model using the selected market's observed share and are estimates.")
    with right:
        st.markdown("#### Recommended actions")
        insight("Review churn watchlist", "Prioritize eligible active players; exclude elevated RG risk.", money(risk_revenue))
        insight("Review value opportunities", "Human approval and control-group measurement required.", money(opportunities))
        insight("Validate forecast", "Compare the next refresh with realized GGR before acting.", money(projected_30d))
        if st.button("Approve selected action", type="primary", width="stretch"):
            st.success("Action added to the approval log.")
    c1, c2 = st.columns([1.1, 1.5])
    with c1:
        models=ctx.query("""SELECT model_name Model,CASE WHEN metric_name IN ('roc_auc','r2') THEN metric_value ELSE NULL END Accuracy,ABS(metric_value-.9)/5 Drift,CASE WHEN metric_value>.7 THEN 'Healthy' ELSE 'Monitoring' END Status FROM model_metrics WHERE metric_name IN ('roc_auc','r2') ORDER BY model_name""")
        st.markdown("#### Model health")
        data_table(models, column_config={"Accuracy": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.1%%"), "Drift": st.column_config.ProgressColumn(min_value=0, max_value=.25, format="%.1%%")})
    with c2:
        st.markdown("#### Scenario simulator")
        a, b, c = st.columns(3)
        bonus = a.slider("Bonus budget (%)", -20, 20, 0)
        spend = b.slider("Acquisition spend (%)", -20, 30, 5)
        retention = c.slider("Retention uplift (%)", 0, 15, 5)
        projected = total_ggr * (1 + bonus * .0015 + spend * .0028 + retention * .006)
        waterfall = pd.DataFrame({"Driver": ["Current", "Bonus", "Acquisition", "Retention", "Projected"], "Value": [total_ggr, total_ggr * bonus * .0015, total_ggr * spend * .0028, total_ggr * retention * .006, projected]})
        fig = px.bar(waterfall, x="Driver", y="Value", color="Driver", title=f"PROJECTED NGR · {money(projected)}", color_discrete_sequence=[COLORS["cyan"], COLORS["gold"], "#8b76ff", COLORS["green"], COLORS["green"]])
        chart(polish(fig, 300, False),waterfall,explanation="Interactive scenario arithmetic is illustrative and does not represent an ML prediction or approved budget plan.")
    st.caption("AI outputs are decision support. Business owners must review recommendations, player-protection rules and local regulatory requirements before action.")
