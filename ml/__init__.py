"""Machine-learning training and scoring for CasinoAI, one project per KPI.

- ml.churn             — churn probability (7/14/30-day horizons)
- ml.ltv               — remaining lifetime value (30/90/180-day horizons)
- ml.revenue_forecast  — daily GGR/NGR/deposits/FTD forecasters
- ml.anomaly_detection — Isolation Forest anomaly detection
- ml.next_best_action  — governed recommendation rules
- ml.shared            — features, model factories and metrics shared by the projects above
- ml.pipeline          — orchestrator; `train_and_score()` is the single public entry point
"""
