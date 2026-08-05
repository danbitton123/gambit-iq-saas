from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS
from data.decision_engine import DecisionAlert, DecisionEngine, RULE_CATALOG
from ui.charts import polish
from ui.components import chart, data_table, kpis, money, pct
from ui.theme import page_header


SEVERITY_ORDER = ["Critical", "High", "Medium"]
STATUS_ORDER = ["New", "Reviewed", "Resolved"]
SEVERITY_ICONS = {"Critical": "crisis_alert", "High": "warning", "Medium": "info"}


def _status(alert: DecisionAlert) -> str:
    return st.session_state.get(f"decision_status_{alert.rule_id}", "New")


def _result(alert: DecisionAlert) -> str:
    value = st.session_state.get(f"decision_result_{alert.rule_id}", "").strip()
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
        "Priority": alert.priority, "Status": _status(alert), "Rule": alert.rule_id,
    } for alert in alerts])


def _alert_card(alert: DecisionAlert) -> None:
    severity = alert.severity.lower()
    impact = money(alert.financial_impact) if alert.financial_impact else "Not monetized"
    st.markdown(
        f"<article class='decision-alert decision-{severity}'><div class='decision-alert-head'>"
        f"<span class='decision-alert-icon material-symbols-rounded'>{SEVERITY_ICONS[alert.severity]}</span>"
        f"<div><small>{alert.severity} · {alert.priority}</small><strong>{alert.title}</strong></div>"
        f"<b>{_status(alert)}</b></div><div class='decision-alert-kpis'>"
        f"<div><span>KPI</span><strong>{alert.kpi}</strong></div><div><span>CURRENT</span><strong>{alert.current_value}</strong></div>"
        f"<div><span>USUAL / LIMIT</span><strong>{alert.usual_value}</strong></div><div><span>FINANCIAL IMPACT</span><strong>{impact}</strong></div>"
        f"</div><div class='decision-alert-explain'><div><span>PROBABLE CAUSE</span><p>{alert.probable_cause}</p></div>"
        f"<div><span>RECOMMENDATION</span><p>{alert.recommendation}</p></div></div>"
        f"<footer><span class='material-symbols-rounded'>groups</span>{alert.team}<span class='material-symbols-rounded'>speed</span>"
        f"{alert.effort} effort<span class='material-symbols-rounded'>verified</span>{alert.confidence:.0%} confidence</footer></article>",
        unsafe_allow_html=True,
    )


def render(ctx) -> None:
    page_header("AI DECISION ENGINE", "Automated anomaly detection, accountable recommendations and action tracking", "Operational Intelligence")
    with st.spinner("Evaluating governed decision rules…"):
        alerts = DecisionEngine(ctx).evaluate()

    for alert in alerts:
        st.session_state.setdefault(f"decision_status_{alert.rule_id}", "New")
        st.session_state.setdefault(f"decision_result_{alert.rule_id}", "")

    critical = sum(alert.severity == "Critical" for alert in alerts)
    financial_impact = sum(alert.financial_impact for alert in alerts)
    potential = sum(alert.revenue_potential for alert in alerts)
    reviewed = sum(_status(alert) in ["Reviewed", "Resolved"] for alert in alerts)
    kpis([
        ("Observed Active Alerts", f"{len(alerts):,}", f"{len(RULE_CATALOG):,} governed rules monitored"),
        ("Observed Critical Alerts", f"{critical:,}", "Immediate executive review"),
        ("Estimated Alert Impact", money(financial_impact), "Non-additive decision-support estimate"),
        ("Estimated Recovery Potential", money(potential), "Severity-adjusted opportunity"),
        ("Observed Reviewed Decisions", f"{reviewed:,} / {len(alerts):,}", "Session action register"),
    ], ctx)

    alerts_tab, recommendations_tab, governance_tab = st.tabs(["Intelligent alerts", "Recommendation center", "Rule governance"])
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
                selected_title = st.selectbox("Open an alert", [f"{a.severity} · {a.title} · {a.team}" for a in filtered], key="decision_selected")
                selected = filtered[[f"{a.severity} · {a.title} · {a.team}" for a in filtered].index(selected_title)]
                _alert_card(selected)
                action_col, result_col = st.columns([1, 2])
                with action_col:
                    st.segmented_control("Alert status", STATUS_ORDER, key=f"decision_status_{selected.rule_id}", width="stretch")
                with result_col:
                    st.text_input("Result after action", key=f"decision_result_{selected.rule_id}", placeholder="Enter a measured result, owner note or follow-up…")
                st.caption("Status and result are stored in the current demo session. Connect an action ledger for durable multi-user workflow.")
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

    st.caption("Decision Engine outputs are decision support. Thresholds, financial impact and recovery potential require owner validation before action.")
