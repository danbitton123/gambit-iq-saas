from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from config import COLORS
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight,kpis,money,pct,period_delta
from ui.theme import page_header

def render(ctx)->None:
    page_header("FINANCIAL COMMAND","Revenue, cash flow and payment intelligence","Finance & Payments")
    tx_sql="""SELECT COALESCE(SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Deposit' THEN amount ELSE 0 END),0) deposits,COALESCE(SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Withdrawal' THEN amount ELSE 0 END),0) withdrawals,COALESCE(SUM(CASE WHEN transaction_status='Approved' THEN processing_fee ELSE 0 END),0) fees,AVG(transaction_status='Approved') approval FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end AND (:country='All markets' OR country=:country)"""
    gaming_sql="""SELECT COALESCE(SUM(bets),0) bets,COALESCE(SUM(payout),0) payout FROM (SELECT SUM(total_bet_amount) bets,SUM(total_payout_amount) payout FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country) UNION ALL SELECT SUM(stake),SUM(payout) FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country))"""
    tx=ctx.query(tx_sql).iloc[0];gaming=ctx.query(gaming_sql).iloc[0]
    previous_tx=ctx.previous_query(tx_sql).iloc[0];previous_gaming=ctx.previous_query(gaming_sql).iloc[0]
    ggr=gaming.bets-gaming.payout;bonus=max(ggr,0)*.065;tax=max(ggr,0)*.095;ngr=ggr-tx.fees-bonus-tax
    previous_ggr=previous_gaming.bets-previous_gaming.payout;previous_ngr=previous_ggr-previous_tx.fees-max(previous_ggr,0)*.065-max(previous_ggr,0)*.095
    kpis([("Estimated NGR",money(ngr),period_delta(ngr,previous_ngr)),("Observed Deposits",money(tx.deposits),period_delta(tx.deposits,previous_tx.deposits)),("Observed Withdrawals",money(tx.withdrawals),period_delta(tx.withdrawals,previous_tx.withdrawals)),("Observed Net Cash Flow",money(tx.deposits-tx.withdrawals),"Approved deposits − withdrawals"),("Observed Payment Approval Rate",pct(tx.approval,2),"Observed transaction approval")],ctx)
    left,middle,right=st.columns([1.7,1.2,1])
    with left:
        fig=go.Figure(go.Waterfall(x=["Total bets","Payouts","GGR","Estimated bonuses","Payment fees","Estimated taxes","Estimated NGR"],y=[gaming.bets,-gaming.payout,0,-bonus,-tx.fees,-tax,0],measure=["absolute","relative","total","relative","relative","relative","total"],decreasing={"marker":{"color":COLORS["red"]}},totals={"marker":{"color":COLORS["green"]}}));fig.update_layout(title="REVENUE WATERFALL ANALYSIS");chart(polish(fig,390,False),explanation="Bets, payouts and payment fees are observed. Bonuses (6.5%) and taxes (9.5%) are explicit demo estimates.")
    with middle:
        weekly=ctx.query("""SELECT DATE(transaction_date,'-'||((CAST(strftime('%w',transaction_date) AS INT)+6)%7)||' day') week,transaction_type,SUM(amount) amount FROM v_transactions_enriched WHERE transaction_status='Approved' AND transaction_date>=:start AND transaction_date<:end AND (:country='All markets' OR country=:country) GROUP BY week,transaction_type ORDER BY week""");weekly.week=pd.to_datetime(weekly.week);chart(polish(px.bar(weekly,x="week",y="amount",color="transaction_type",barmode="group",title="DEPOSITS VS WITHDRAWALS",color_discrete_map={"Deposit":COLORS["green"],"Withdrawal":COLORS["gold"]}),390),weekly,explanation="Approved transaction value grouped by calendar week.")
    with right: st.markdown("<p class='panel-title'>Financial anomalies</p>",unsafe_allow_html=True);insight("Withdrawal spike","Compare with seven-day baseline.","Review liquidity",True);insight("Payment decline","Approval changes require review.","MEDIUM",True)
    methods=ctx.query("""SELECT payment_method,SUM(amount) Volume,COUNT(*) Transactions,AVG(transaction_status='Approved') Approved,AVG(transaction_status='Declined') Declined,SUM(processing_fee) Fees,SUM(processing_fee)/NULLIF(SUM(amount),0) Avg_fee FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end AND (:country='All markets' OR country=:country) GROUP BY payment_method ORDER BY Volume DESC""");st.markdown("#### Payment-method performance");data_table(methods,column_config={"Volume":st.column_config.NumberColumn(format="$%.0f"),"Approved":st.column_config.ProgressColumn(min_value=0,max_value=1,format="%.1%%"),"Declined":st.column_config.ProgressColumn(min_value=0,max_value=1,format="%.1%%"),"Fees":st.column_config.NumberColumn(format="$%.0f"),"Avg_fee":st.column_config.NumberColumn("Fee rate",format="%.2%%")})
    daily=ctx.query("""SELECT metric_date date,SUM(total_ggr) GGR FROM mart_executive_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country) GROUP BY metric_date ORDER BY metric_date""");daily.date=pd.to_datetime(daily.date)
    country=ctx.query("""SELECT country,SUM(lifetime_ggr) lifetime_ggr FROM v_player_scores WHERE (:country='All markets' OR country=:country) GROUP BY country ORDER BY lifetime_ggr""")
    c1,c2,c3=st.columns(3)
    with c1: chart(polish(px.line(daily,x="date",y="GGR",title="REVENUE TREND · SQL"),310,False),daily,explanation="Observed casino and sportsbook GGR.")
    with c2: chart(polish(px.bar(country,x="lifetime_ggr",y="country",orientation="h",title="LIFETIME GGR CONTEXT",color_discrete_sequence=[COLORS["cyan"]]),310,False),country,explanation="Lifetime context for the selected market; not period profitability.")
    with c3: chart(polish(go.Figure(go.Indicator(mode="gauge+number",value=float(tx.approval or 0)*100,number={"suffix":"%"},gauge={"axis":{"range":[0,100]},"bar":{"color":COLORS["green"]}},title={"text":"PAYMENT APPROVAL"})),310,False),explanation="Observed approval rate for transactions matching the global filters.")
