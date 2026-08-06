from __future__ import annotations

"""Per-channel acquisition quality: FTD D30 conversion, CAC, predicted ROAS/retention proxies and a composite demo quality score."""

from .cohort_base import BASE_SQL

SQL = BASE_SQL + """SELECT channel,COUNT(*) Players,SUM(converted_d30) FTD_D30,1.0*SUM(converted_d30)/NULLIF(COUNT(*),0) FTD_Conversion_D30,AVG(acquisition_cost) CAC,AVG(predicted_ltv_90d) Predicted_LTV_Proxy,AVG(predicted_ltv_90d/acquisition_cost) Predicted_ROAS_Proxy,AVG(fraud_risk) Fraud_Risk,1-AVG(churn_probability) Predicted_Retention_Proxy,100*AVG(predicted_ltv_90d/acquisition_cost)*(1-AVG(churn_probability))*(1-AVG(fraud_risk))/10 Quality_Score FROM b GROUP BY channel ORDER BY Quality_Score DESC"""


def run(ctx):
    return ctx.query(SQL)
