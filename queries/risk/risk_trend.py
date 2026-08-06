from __future__ import annotations

"""Daily average fraud, RG and churn model scores by players' last observed session date."""

SQL = """SELECT DATE(last_session) date,'Fraud' Risk,AVG(fraud_risk)*100 Score FROM v_player_scores v WHERE last_session>=:start AND last_session<:end AND (:country='All markets' OR v.country=:country) GROUP BY date UNION ALL SELECT DATE(last_session),'Responsible gaming',AVG(rg_risk)*100 FROM v_player_scores v WHERE last_session>=:start AND last_session<:end AND (:country='All markets' OR v.country=:country) GROUP BY DATE(last_session) UNION ALL SELECT DATE(last_session),'Churn',AVG(churn_probability)*100 FROM v_player_scores v WHERE last_session>=:start AND last_session<:end AND (:country='All markets' OR v.country=:country) GROUP BY DATE(last_session) ORDER BY date"""


def run(ctx):
    return ctx.query(SQL)
