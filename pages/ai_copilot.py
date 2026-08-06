from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS
from data.copilot import GovernedCopilot, SUGGESTED_QUESTIONS, approved_catalog
from data.decision_engine import DecisionAlert, DecisionEngine, RULE_CATALOG
from ui.charts import polish
from ui.components import chart, data_table, kpis, money, pct
from ui.theme import page_header
from ui.copilot_assistant import render_copilot_visual


SEVERITY_ORDER = ["Critical", "High", "Medium"]
STATUS_ORDER = ["New", "Reviewed", "Resolved"]
SEVERITY_ICONS = {"Critical": "crisis_alert", "High": "warning", "Medium": "info"}


def _analysis_markdown(item: dict) -> str:
    response = item["response"]
    sources = "\n".join(f"- {source}" for source in response.sources)
    evidence = f"```csv\n{response.evidence.to_csv(index=False)}```" if not response.evidence.empty else "No result rows."
    return f"""# {response.title}

**Question:** {item['question']}

**Scope:** {item['scope']}

## Answer

{response.answer}

## Evidence

{evidence}

## Data used

{sources}

## Confidence and limitations

- Confidence: {response.confidence:.0%}
- {response.limitations}
"""


def _render_copilot_response(item: dict, index: int) -> None:
    response = item["response"]
    with st.chat_message("user"):
        st.write(item["question"])
    with st.chat_message("assistant"):
        if response.refused:
            st.warning(response.answer, icon=":material/shield:")
        else:
            st.markdown(f"### {response.title}")
            st.write(response.answer)
            render_copilot_visual(response)
            if not response.evidence.empty:
                with st.expander("View governed evidence", expanded=index == 0):
                    data_table(response.evidence)
        st.markdown(
            f"<div class='copilot-confidence'><span><i class='material-symbols-rounded'>verified</i>"
            f"{response.confidence:.0%} confidence</span><span><i class='material-symbols-rounded'>filter_alt</i>"
            f"{item['scope']}</span></div>", unsafe_allow_html=True,
        )
        st.caption(f"Limit: {response.limitations}")
        st.markdown("**Data used**")
        for source in response.sources:
            st.caption(f"↳ {source}")
        action1, action2, action3 = st.columns([1, 1, 2.2])
        with action1:
            if st.button("Useful", icon=":material/thumb_up:", key=f"copilot_useful_{item['id']}"):
                st.session_state[f"copilot_feedback_{item['id']}"] = "Useful"
        with action2:
            if st.button("Not useful", icon=":material/thumb_down:", key=f"copilot_not_useful_{item['id']}"):
                st.session_state[f"copilot_feedback_{item['id']}"] = "Not useful"
        with action3:
            feedback = st.session_state.get(f"copilot_feedback_{item['id']}")
            if feedback:
                st.caption(f"Feedback recorded: {feedback}")


def _render_copilot(ctx, alerts) -> None:
    st.markdown("""<section class='copilot-hero'><div><small>GOVERNED BUSINESS COPILOT</small>
      <h2>Ask anything about your operation.</h2><p>Open analysis across governed client data—with evidence, insights and charts.</p></div>
      <span class='material-symbols-rounded'>forum</span></section>""", unsafe_allow_html=True)
    st.info("The Copilot converts natural language into a validated read-only semantic query, applies the global filters, anonymizes player evidence and cites every source.", icon=":material/security:")
    st.session_state.setdefault("copilot_history", [])
    copilot = GovernedCopilot(ctx, alerts)

    st.markdown("#### Suggested questions")
    suggestion_cols = st.columns(3)
    selected_question = None
    for index, suggestion in enumerate(SUGGESTED_QUESTIONS):
        with suggestion_cols[index % 3]:
            if st.button(suggestion, key=f"copilot_suggestion_{index}", width="stretch"):
                selected_question = suggestion
    question = st.chat_input("Ask any question about the client’s casino and sportsbook data…", key="copilot_question")
    question = question or selected_question
    if question:
        previous_response=st.session_state.copilot_history[0]["response"] if st.session_state.copilot_history else None
        previous_intent=previous_response.intent if previous_response else None
        response=copilot.ask(question,previous_intent=previous_intent,page_context="AI Copilot",previous_response=previous_response)
        st.session_state.copilot_history.insert(0, {
            "id": f"{len(st.session_state.copilot_history)+1}_{abs(hash(question))}",
            "question": question, "scope": ctx.period_label, "response": response,
        })

    history = st.session_state.copilot_history
    if not history:
        st.markdown("<div class='copilot-empty'><span class='material-symbols-rounded'>travel_explore</span><strong>Start with a suggested question</strong><small>The response will include evidence, scope, confidence and limitations.</small></div>", unsafe_allow_html=True)
    else:
        top, controls = st.columns([2, 1])
        with top: st.markdown(f"#### Conversation history · {len(history)} question{'s' if len(history)!=1 else ''}")
        with controls:
            if st.button("Clear history", icon=":material/delete_sweep:", width="stretch"):
                st.session_state.copilot_history = []
                st.rerun()
        for index, item in enumerate(history):
            _render_copilot_response(item, index)
        export = "\n\n---\n\n".join(_analysis_markdown(item) for item in reversed(history))
        st.download_button("Download complete analysis", export, "casino_ai_copilot_analysis.md", "text/markdown", icon=":material/download:", width="stretch")

    with st.expander("Available data domains and safety policy"):
        data_table(approved_catalog())
        st.markdown("""
        - User text is never inserted into SQL.
        - Flexible questions compile into an allow-listed semantic plan; model-generated text never becomes SQL.
        - Direct player identifiers and personal data are never returned.
        - Questions about the operator’s data are analyzed openly; unrelated or sensitive requests cannot reach the warehouse.
        - Outputs are decision support and never execute campaigns, limits or player-protection actions.
        """)


def _status(alert: DecisionAlert) -> str:
    return st.session_state.get(f"decision_status_{alert.workflow_id}", "New")


def _result(alert: DecisionAlert) -> str:
    value = st.session_state.get(f"decision_result_{alert.workflow_id}", "").strip()
    if value:
        return value
    if _status(alert) == "Resolved":
        return "Resolved · outcome measurement pending"
    if _status(alert) == "Reviewed":
        return "Baseline reviewed · action pending"
    return "No action taken"


def _alert_frame(alerts: list[DecisionAlert]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Alert": alert.title, "Severity": alert.severity, "KPI": alert.kpi,
        "Current": alert.current_value, "Usual": alert.usual_value,
        "Financial impact": alert.financial_impact, "Team": alert.team,
        "Priority": alert.priority, "Market": alert.market, "Status": _status(alert), "Rule": alert.rule_id,
    } for alert in alerts])


def _alert_card(alert: DecisionAlert) -> None:
    severity = alert.severity.lower()
    impact = money(alert.financial_impact) if alert.financial_impact else "Not monetized"
    st.markdown(
        f"<article class='decision-alert decision-{severity}'><div class='decision-alert-head'>"
        f"<span class='decision-alert-icon material-symbols-rounded'>{SEVERITY_ICONS[alert.severity]}</span>"
        f"<div><small>{alert.severity} · {alert.priority} · {alert.market}</small><strong>{alert.title}</strong></div>"
        f"<b>{_status(alert)}</b></div><div class='decision-alert-kpis'>"
        f"<div><span>KPI</span><strong>{alert.kpi}</strong></div><div><span>CURRENT</span><strong>{alert.current_value}</strong></div>"
        f"<div><span>USUAL / LIMIT</span><strong>{alert.usual_value}</strong></div><div><span>FINANCIAL IMPACT</span><strong>{impact}</strong></div>"
        f"</div><div class='decision-alert-explain'><div><span>PROBABLE CAUSE</span><p>{alert.probable_cause}</p></div>"
        f"<div><span>RECOMMENDATION</span><p>{alert.recommendation}</p></div></div>"
        f"<footer><span class='material-symbols-rounded'>groups</span>{alert.team}<span class='material-symbols-rounded'>speed</span>"
        f"{alert.effort} effort<span class='material-symbols-rounded'>verified</span>{alert.confidence:.0%} confidence</footer></article>",
        unsafe_allow_html=True,
    )


def _render_ml_lab(ctx) -> None:
    metrics = ctx.repo.query("""SELECT model_name,horizon_days,split,metric_name,metric_value,model_version,measured_at
        FROM model_metrics_v2 ORDER BY model_name,split,metric_name""")
    forecasts = ctx.query("""SELECT metric,forecast_date,actual_value,predicted_value,lower_bound,upper_bound,split
        FROM forecast_backtest WHERE forecast_date>=DATE(:start) AND forecast_date<DATE(:end) ORDER BY forecast_date""")
    anomalies = ctx.query("""SELECT detected_date,metric,current_value,usual_value,anomaly_score,severity,method
        FROM ml_anomalies WHERE detected_date>=DATE(:start) AND detected_date<DATE(:end)
        ORDER BY anomaly_score DESC""")
    actions = ctx.repo.query("""SELECT recommended_action,COUNT(*) players,SUM(estimated_value_at_stake) value_at_stake,
        AVG(action_confidence) confidence FROM next_best_actions GROUP BY recommended_action ORDER BY value_at_stake DESC""")

    test_metrics = metrics[metrics.split.eq("test")]
    churn_auc = test_metrics[(test_metrics.model_name.eq("churn_30d")) & (test_metrics.metric_name.eq("roc_auc"))]
    churn_lift = test_metrics[(test_metrics.model_name.eq("churn_30d")) & (test_metrics.metric_name.eq("lift_top_10pct"))]
    forecast_wape = test_metrics[(test_metrics.model_name.eq("forecast_ggr")) & (test_metrics.metric_name.eq("wape"))]
    kpis([
        ("Test Churn ROC-AUC 30D", pct(churn_auc.metric_value.iloc[0] if not churn_auc.empty else None, 3), "Latest untouched temporal test"),
        ("Test Churn Lift · Top 10%", f"{churn_lift.metric_value.iloc[0]:.2f}x" if not churn_lift.empty else "Missing data", "Risk concentration versus baseline"),
        ("Test GGR Forecast Accuracy", pct(1-forecast_wape.metric_value.iloc[0] if not forecast_wape.empty else None, 2), "1 − WAPE on latest test window"),
        ("Detected ML Anomalies", f"{len(anomalies):,}", "Selected period · Isolation Forest"),
        ("Players with Active NBA", f"{int(actions.loc[~actions.recommended_action.eq('Do nothing'),'players'].sum()):,}" if not actions.empty else "Missing data", "Human review required"),
    ], ctx)

    st.markdown("<div class='ml-policy'><span class='material-symbols-rounded'>verified_user</span><div><small>LEAKAGE CONTROL</small><strong>Past training → recent validation → latest untouched test</strong><p>Every horizon owns its observation window. Test performance is frozen before final refitting.</p></div></div>", unsafe_allow_html=True)
    performance_tab, forecast_tab, anomaly_tab, nba_tab = st.tabs(["Model performance", "Forecast backtests", "Anomalies", "Next Best Action"])
    with performance_tab:
        selector, split_col = st.columns([1.4, 1])
        model_options = sorted(metrics.model_name.unique())
        with selector: selected_model = st.selectbox("Model", model_options, key="ml_model_selector")
        with split_col: selected_split = st.segmented_control("Evaluation split", ["validation", "test"], default="test", key="ml_split")
        selected = metrics[(metrics.model_name.eq(selected_model)) & (metrics.split.eq(selected_split or "test"))]
        left, right = st.columns([1.15, 1.85])
        with left:
            st.markdown("#### Audited scorecard")
            data_table(selected[["metric_name","metric_value","horizon_days","model_version"]].rename(columns={"metric_name":"Metric","metric_value":"Value","horizon_days":"Horizon (days)","model_version":"Version"}))
        with right:
            plot = selected[selected.metric_name.isin(["roc_auc","precision","recall","lift_top_10pct","wape","interval_80_coverage"])].copy()
            if not plot.empty:
                fig = px.bar(plot, x="metric_name", y="metric_value", color="metric_name", text_auto=".3f", title="OUT-OF-TIME PERFORMANCE")
                fig.update_layout(showlegend=False)
                chart(polish(fig, 360, False), plot, explanation="Metrics come only from the selected chronological validation or untouched test window.")
        st.caption("Revenue actually saved after campaign requires a connected campaign-assignment and outcome ledger. It is intentionally not fabricated in the demo.")
    with forecast_tab:
        if forecasts.empty:
            st.info("No forecast backtest falls inside the selected period.")
        else:
            metric = st.selectbox("Forecast target", sorted(forecasts.metric.unique()), key="forecast_target")
            view = forecasts[forecasts.metric.eq(metric)].copy(); view["forecast_date"] = pd.to_datetime(view.forecast_date)
            fig = px.line(view, x="forecast_date", y=["actual_value","predicted_value"], title=f"{metric.upper()} · PREDICTION VS ACTUAL")
            fig.add_scatter(x=view.forecast_date, y=view.upper_bound, mode="lines", line={"width":0}, showlegend=False)
            fig.add_scatter(x=view.forecast_date, y=view.lower_bound, mode="lines", fill="tonexty", line={"width":0}, name="80% interval", fillcolor="rgba(39,209,127,.14)")
            chart(polish(fig, 420), view, explanation="Chronological backtest. The shaded 80% empirical interval is calibrated from validation residuals.")
    with anomaly_tab:
        if anomalies.empty: st.success("No anomaly was detected in the selected period.")
        else:
            data_table(anomalies, column_config={"current_value":st.column_config.NumberColumn("Current",format="%.2f"),"usual_value":st.column_config.NumberColumn("Usual",format="%.2f"),"anomaly_score":st.column_config.ProgressColumn("Anomaly score",min_value=0,max_value=max(float(anomalies.anomaly_score.max()),1),format="%.3f")})
    with nba_tab:
        left, right = st.columns([1.35, 1])
        with left:
            data_table(actions, column_config={"value_at_stake":st.column_config.NumberColumn("Estimated value at stake",format="$%.0f"),"confidence":st.column_config.ProgressColumn(min_value=0,max_value=1,format="%.1%%")})
        with right:
            actionable = actions[~actions.recommended_action.eq("Do nothing")]
            if not actionable.empty:
                fig = px.bar(actionable, x="players", y="recommended_action", orientation="h", color="value_at_stake", title="ACTIONABLE PLAYER QUEUE", color_continuous_scale=[COLORS["cyan"],COLORS["green"]])
                chart(polish(fig, 380, False), actionable, explanation="Actions are ranked decision support. RG and fraud safeguards override commercial actions.")
        st.warning("Next Best Action never executes automatically. Responsible Gaming suppression and manual-review rules take precedence over commercial recommendations.")


def render(ctx) -> None:
    page_header("AI COPILOT", "Conversational analytics, intelligent alerts and accountable action tracking", "Operational Intelligence")
    with st.spinner("Evaluating governed decision rules…"):
        alerts = DecisionEngine(ctx).evaluate()

    for alert in alerts:
        st.session_state.setdefault(f"decision_status_{alert.workflow_id}", "New")
        st.session_state.setdefault(f"decision_result_{alert.workflow_id}", "")

    active_alerts = [alert for alert in alerts if _status(alert) != "Resolved"]
    critical = sum(alert.severity == "Critical" for alert in active_alerts)
    financial_impact = sum(alert.financial_impact for alert in active_alerts)
    potential = sum(alert.revenue_potential for alert in active_alerts)
    reviewed = sum(_status(alert) in ["Reviewed", "Resolved"] for alert in alerts)
    kpis([
        ("Observed Active Alerts", f"{len(active_alerts):,}", f"{len(alerts)-len(active_alerts):,} resolved · {len(RULE_CATALOG):,} rules per market"),
        ("Observed Critical Alerts", f"{critical:,}", "Immediate executive review"),
        ("Estimated Alert Impact", money(financial_impact), "Non-additive decision-support estimate"),
        ("Estimated Recovery Potential", money(potential), "Severity-adjusted opportunity"),
        ("Observed Reviewed Decisions", f"{reviewed:,} / {len(alerts):,}", "Session action register"),
    ], ctx)

    copilot_tab, alerts_tab, recommendations_tab, governance_tab, ml_tab = st.tabs(["AI conversation", "Intelligent alerts", "Recommendation center", "Rule governance", "ML Intelligence"])
    with copilot_tab:
        _render_copilot(ctx, alerts)
    with alerts_tab:
        if not alerts:
            st.success("No governed threshold is breached for the selected period and market.")
        else:
            f1, f2, f3 = st.columns([1, 1, 1.25])
            with f1:
                severities = st.multiselect("Severity", SEVERITY_ORDER, default=SEVERITY_ORDER, key="decision_severity")
            with f2:
                statuses = st.multiselect("Status", STATUS_ORDER, default=STATUS_ORDER, key="decision_status_filter")
            with f3:
                teams = sorted({alert.team for alert in alerts})
                selected_teams = st.multiselect("Responsible team", teams, default=teams, key="decision_team")
            filtered = [alert for alert in alerts if alert.severity in severities and _status(alert) in statuses and alert.team in selected_teams]
            if not filtered:
                st.info("No alert matches the selected queue filters.")
            else:
                st.markdown("#### Alert action desk")
                st.caption("Update every alert independently. KPI counters refresh immediately; the same country alert keeps its status in country and all-market views.")
                for index, alert in enumerate(filtered):
                    label = f"{alert.severity} · {alert.market} · {alert.title} · {_status(alert)}"
                    with st.expander(label, expanded=index == 0):
                        _alert_card(alert)
                        action_col, result_col = st.columns([1, 2])
                        with action_col:
                            st.segmented_control("Alert status", STATUS_ORDER, key=f"decision_status_{alert.workflow_id}", width="stretch")
                        with result_col:
                            st.text_input("Result after action", key=f"decision_result_{alert.workflow_id}", placeholder="Enter a measured result, owner note or follow-up…")
                queue = _alert_frame(filtered)
                st.markdown("#### Active alert queue")
                data_table(queue.drop(columns=["Rule"]), column_config={
                    "Financial impact": st.column_config.NumberColumn(format="$%.0f"),
                    "Severity": st.column_config.TextColumn(), "Status": st.column_config.TextColumn(),
                })

    with recommendations_tab:
        if not alerts:
            st.info("Recommendations will appear when a governed rule is triggered.")
        else:
            recommendation_rows = pd.DataFrame([{
                "Recommendation": alert.recommendation,
                "Responsible team": alert.team,
                "Potential revenue": alert.revenue_potential,
                "Estimated effort": alert.effort,
                "Priority": alert.priority,
                "Market": alert.market,
                "Confidence": alert.confidence,
                "Date": alert.detected_at,
                "Status": _status(alert),
                "Result after action": _result(alert),
            } for alert in alerts])
            left, right = st.columns([1.45, 1])
            with left:
                st.markdown("#### Operational recommendation register")
                data_table(recommendation_rows, column_config={
                    "Potential revenue": st.column_config.NumberColumn(format="$%.0f"),
                    "Confidence": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.0f%%"),
                    "Date": st.column_config.TextColumn(),
                })
            with right:
                impact_by_team = recommendation_rows.groupby("Responsible team", as_index=False)["Potential revenue"].sum().sort_values("Potential revenue")
                fig = px.bar(impact_by_team, x="Potential revenue", y="Responsible team", orientation="h",
                             color="Potential revenue", title="RECOVERY POTENTIAL BY OWNER",
                             color_continuous_scale=[COLORS["cyan"], COLORS["green"]])
                fig.update_layout(coloraxis_showscale=False)
                chart(polish(fig, 390, False), impact_by_team, explanation="Severity-adjusted estimate used to prioritize investigation; opportunities are non-additive and require validation.")
            st.markdown("#### Decision cards")
            card_cols = st.columns(2)
            for index, alert in enumerate(alerts):
                with card_cols[index % 2]:
                    st.markdown(
                        f"<article class='recommendation-action'><header><span>{alert.priority}</span><strong>{alert.title}</strong></header>"
                        f"<p>{alert.recommendation}</p><div><span>OWNER<strong>{alert.team}</strong></span>"
                        f"<span>POTENTIAL<strong>{money(alert.revenue_potential)}</strong></span>"
                        f"<span>EFFORT<strong>{alert.effort}</strong></span><span>CONFIDENCE<strong>{alert.confidence:.0%}</strong></span></div>"
                        f"<footer>{_status(alert)} · {_result(alert)}</footer></article>", unsafe_allow_html=True,
                    )

    with governance_tab:
        st.info("Rules are deterministic and auditable. Predicted rules prioritize human review; they never execute commercial, fraud or player-protection actions automatically.")
        rules = pd.DataFrame([{
            "Rule ID": rule_id, "Detection": values[0], "KPI": values[1], "Owner": values[2],
            "Threshold": values[3], "Evaluation": "Triggered" if any(alert.rule_id == rule_id for alert in alerts) else "Within threshold",
        } for rule_id, values in RULE_CATALOG.items()])
        data_table(rules)
        st.markdown("#### Operating model")
        steps = st.columns(5)
        for col, icon, title, body in zip(steps,
            ["database", "rule", "assignment_ind", "task_alt", "monitoring"],
            ["Detect", "Explain", "Assign", "Act", "Measure"],
            ["Governed SQL snapshot", "Threshold + probable cause", "Named accountable team", "Human-approved response", "Record verified outcome"]):
            with col:
                st.markdown(f"<div class='decision-step'><span class='material-symbols-rounded'>{icon}</span><strong>{title}</strong><small>{body}</small></div>", unsafe_allow_html=True)

    with ml_tab:
        _render_ml_lab(ctx)

    st.caption("Decision Engine outputs are decision support. Thresholds, financial impact and recovery potential require owner validation before action.")
