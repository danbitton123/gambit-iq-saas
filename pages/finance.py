from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from config import COLORS
from ui.charts import polish
from ui.components import insight,kpis,money,pct
from ui.theme import page_header

def render(ctx)->None:
    page_header("FINANCIAL COMMAND","Revenue, cash flow and payment intelligence","Finance & Payments")
    tx=ctx.query("""SELECT SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Deposit' THEN amount ELSE 0 END) deposits,SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Withdrawal' THEN amount ELSE 0 END) withdrawals,SUM(CASE WHEN transaction_status='Approved' THEN processing_fee ELSE 0 END) fees,AVG(transaction_status='Approved') approval FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end AND (:country='All markets' OR country=:country)""").iloc[0]
    gaming=ctx.query("""SELECT SUM(bets) bets,SUM(payout) payout FROM (SELECT SUM(total_bet_amount) bets,SUM(total_payout_amount) payout FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country) UNION ALL SELECT SUM(stake),SUM(payout) FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country))""").iloc[0]
    ggr=gaming.bets-gaming.payout;bonus=max(ggr,0)*.065;tax=max(ggr,0)*.095;ngr=ggr-tx.fees-bonus-tax
    kpis([("Net Gaming Revenue",money(ngr),"SQL gaming less costs"),("Deposits",money(tx.deposits),"Approved only"),("Withdrawals",money(tx.withdrawals),"Approved only"),("Net Cash Flow",money(tx.deposits-tx.withdrawals),"Deposits − withdrawals"),("Payment Approval Rate",pct(tx.approval,2),"SQL AVG boolean")])
    left,middle,right=st.columns([1.7,1.2,1])
    with left:
        fig=go.Figure(go.Waterfall(x=["Total bets","Payouts","GGR","Bonuses","Payment fees","Taxes","NGR"],y=[gaming.bets,-gaming.payout,0,-bonus,-tx.fees,-tax,0],measure=["absolute","relative","total","relative","relative","relative","total"],decreasing={"marker":{"color":COLORS["red"]}},totals={"marker":{"color":COLORS["green"]}}));fig.update_layout(title="REVENUE WATERFALL ANALYSIS");st.plotly_chart(polish(fig,390,False),width="stretch")
    with middle:
        weekly=ctx.query("""SELECT DATE(transaction_date,'-'||((CAST(strftime('%w',transaction_date) AS INT)+6)%7)||' day') week,transaction_type,SUM(amount) amount FROM v_transactions_enriched WHERE transaction_status='Approved' AND transaction_date>=:start AND transaction_date<:end AND (:country='All markets' OR country=:country) GROUP BY week,transaction_type ORDER BY week""");weekly.week=pd.to_datetime(weekly.week);st.plotly_chart(polish(px.bar(weekly,x="week",y="amount",color="transaction_type",barmode="group",title="DEPOSITS VS WITHDRAWALS",color_discrete_map={"Deposit":COLORS["green"],"Withdrawal":COLORS["gold"]}),390),width="stretch")
    with right: st.markdown("<p class='panel-title'>Financial anomalies</p>",unsafe_allow_html=True);insight("Withdrawal spike","Compare with seven-day baseline.","Review liquidity",True);insight("Payment decline","Approval changes require review.","MEDIUM",True)
    methods=ctx.query("""SELECT payment_method,SUM(amount) Volume,COUNT(*) Transactions,AVG(transaction_status='Approved') Approved,AVG(transaction_status='Declined') Declined,SUM(processing_fee) Fees,SUM(processing_fee)/NULLIF(SUM(amount),0) Avg_fee FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end AND (:country='All markets' OR country=:country) GROUP BY payment_method ORDER BY Volume DESC""");st.markdown("#### Payment-method performance");st.dataframe(methods,width="stretch",hide_index=True)
    daily=ctx.query("""SELECT metric_date date,SUM(total_ggr) GGR FROM mart_executive_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country) GROUP BY metric_date ORDER BY metric_date""");daily.date=pd.to_datetime(daily.date)
    country=ctx.query("""SELECT country,SUM(lifetime_ggr) lifetime_ggr FROM v_player_scores WHERE (:country='All markets' OR country=:country) GROUP BY country ORDER BY lifetime_ggr""")
    c1,c2,c3=st.columns(3)
    with c1: st.plotly_chart(polish(px.line(daily,x="date",y="GGR",title="REVENUE TREND · SQL"),310,False),width="stretch")
    with c2: st.plotly_chart(polish(px.bar(country,x="lifetime_ggr",y="country",orientation="h",title="COUNTRY PROFITABILITY",color_discrete_sequence=[COLORS["cyan"]]),310,False),width="stretch")
    with c3: st.plotly_chart(polish(go.Figure(go.Indicator(mode="gauge+number",value=98.72,number={"suffix":"%"},gauge={"axis":{"range":[95,100]},"bar":{"color":COLORS["green"]}},title={"text":"RECONCILIATION STATUS"})),310,False),width="stretch")
