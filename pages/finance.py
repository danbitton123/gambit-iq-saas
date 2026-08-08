from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from config import COLORS
from data.decision_engine import DecisionEngine
from queries.finance import (
    daily_approval_rate, daily_ggr, gaming_summary,
    payment_methods, transactions_summary, weekly_deposits_withdrawals,
)
from ui.charts import polish
from ui.components import chart, data_table, kpis, money, pct, period_delta, team_alert_block
from ui.theme import page_header

TEAM = {"Revenue & Finance", "Payments"}

def render(ctx)->None:
    page_header("FINANCIAL COMMAND","Revenue, cash flow and payment intelligence","Finance & Payments")
    tx=transactions_summary.run(ctx);gaming=gaming_summary.run(ctx)
    previous_tx=transactions_summary.run_previous(ctx);previous_gaming=gaming_summary.run_previous(ctx)
    ggr=gaming.bets-gaming.payout;bonus=max(ggr,0)*.065;tax=max(ggr,0)*.095;ngr=ggr-tx.fees-bonus-tax
    previous_ggr=previous_gaming.bets-previous_gaming.payout;previous_ngr=previous_ggr-previous_tx.fees-max(previous_ggr,0)*.065-max(previous_ggr,0)*.095
    kpis([("Estimated NGR",money(ngr),period_delta(ngr,previous_ngr)),("Observed Deposits",money(tx.deposits),period_delta(tx.deposits,previous_tx.deposits)),("Observed Withdrawals",money(tx.withdrawals),period_delta(tx.withdrawals,previous_tx.withdrawals)),("Observed Net Cash Flow",money(tx.deposits-tx.withdrawals),"Approved deposits − withdrawals"),("Observed Payment Approval Rate",pct(tx.approval,2),"Observed transaction approval")],ctx)
    left,middle=st.columns([1.5,1.3],gap="medium")
    with left:
        fig=go.Figure(go.Waterfall(x=["Total bets","Payouts","GGR","Estimated bonuses","Payment fees","Estimated taxes","Estimated NGR"],y=[gaming.bets,-gaming.payout,0,-bonus,-tx.fees,-tax,0],measure=["absolute","relative","total","relative","relative","relative","total"],decreasing={"marker":{"color":COLORS["red"]}},totals={"marker":{"color":COLORS["green"]}}));fig.update_layout(title="REVENUE WATERFALL ANALYSIS");chart(polish(fig,390,False),explanation="Bets, payouts and payment fees are observed. Bonuses (6.5%) and taxes (9.5%) are explicit demo estimates.")
    with middle:
        weekly=weekly_deposits_withdrawals.run(ctx);weekly.week=pd.to_datetime(weekly.week);chart(polish(px.bar(weekly,x="week",y="amount",color="transaction_type",barmode="group",title="DEPOSITS VS WITHDRAWALS",color_discrete_map={"Deposit":COLORS["green"],"Withdrawal":COLORS["gold"]}),390),weekly,explanation="Approved transaction value grouped by calendar week.")

    st.markdown("### Revenue & Finance / Payments alerts")
    with st.spinner("Evaluating governed decision rules…"):
        alerts = DecisionEngine(ctx).evaluate()
    team_alert_block(alerts, TEAM, empty_message="No GGR decline or withdrawal spike is currently triggered for this scope.")

    methods=payment_methods.run(ctx);st.markdown("#### Payment-method performance");data_table(methods,column_config={"Volume":st.column_config.NumberColumn(format="$%.0f"),"Approved":st.column_config.ProgressColumn(min_value=0,max_value=1,format="%.1%%"),"Declined":st.column_config.ProgressColumn(min_value=0,max_value=1,format="%.1%%"),"Fees":st.column_config.NumberColumn(format="$%.0f"),"Avg_fee":st.column_config.NumberColumn("Fee rate",format="%.2%%")})
    daily=daily_ggr.run(ctx);daily.date=pd.to_datetime(daily.date)
    approval=daily_approval_rate.run(ctx);approval.date=pd.to_datetime(approval.date)
    c1,c2=st.columns(2,gap="medium")
    with c1: chart(polish(px.line(daily,x="date",y="GGR",title="REVENUE TREND · SQL"),330,False),daily,explanation="Observed casino and sportsbook GGR.")
    with c2:
        approval_fig=px.line(approval,x="date",y="approval_rate",title="PAYMENT APPROVAL RATE · DAILY")
        approval_fig.update_yaxes(tickformat=".0%")
        chart(polish(approval_fig,330,False),approval,explanation="Observed share of payment transactions approved, by day.")
