-- POST-ML MARTS: build only after model_scores exists.
DROP VIEW IF EXISTS mart_player_360;
CREATE VIEW mart_player_360 AS
SELECT p.*,m.predicted_ltv_90d,m.churn_probability,m.fraud_risk,m.rg_risk,
       m.recommended_action,m.model_confidence,m.last_session,m.session_count,m.lifetime_ggr,m.model_version,m.scored_at,
       f.ftd_at,f.ftd_date,a.first_activity_date
FROM dim_player p JOIN model_scores m USING(player_id)
LEFT JOIN int_player_first_deposit f USING(player_id)
LEFT JOIN int_player_first_activity a USING(player_id);

DROP VIEW IF EXISTS v_player_scores;
CREATE VIEW v_player_scores AS SELECT * FROM mart_player_360;
