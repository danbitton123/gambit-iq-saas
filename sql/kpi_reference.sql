-- GAMBIT IQ KPI reference queries — Definition version 1.1
-- Parameters use half-open intervals: :start inclusive, :end exclusive.

-- 1–3. Total GGR, provisional NGR and GGR margin
WITH gaming AS (
    SELECT SUM(total_bet_amount) AS wagers,
           SUM(total_payout_amount) AS payouts
    FROM v_sessions_enriched
    WHERE session_start >= :start AND session_start < :end
      AND (:country = 'All markets' OR country = :country)
    UNION ALL
    SELECT SUM(stake), SUM(payout)
    FROM v_sports_bets_enriched
    WHERE bet_date >= :start AND bet_date < :end
      AND (:country = 'All markets' OR country = :country)
), fees AS (
    SELECT COALESCE(SUM(processing_fee), 0) AS payment_fees
    FROM v_transactions_enriched
    WHERE transaction_status = 'Approved'
      AND transaction_date >= :start AND transaction_date < :end
      AND (:country = 'All markets' OR country = :country)
), totals AS (
    SELECT SUM(wagers) AS wagers, SUM(payouts) AS payouts,
           SUM(wagers) - SUM(payouts) AS ggr
    FROM gaming
)
SELECT wagers, payouts, ggr,
       ggr / NULLIF(wagers, 0) AS ggr_margin,
       ggr - payment_fees - MAX(ggr, 0) * 0.065 - MAX(ggr, 0) * 0.095
           AS estimated_ngr_mvp
FROM totals CROSS JOIN fees;

-- 4. Active players across both products, de-duplicated
SELECT COUNT(DISTINCT player_id) AS active_players
FROM (
    SELECT player_id FROM v_sessions_enriched
    WHERE session_start >= :start AND session_start < :end
      AND (:country = 'All markets' OR country = :country)
    UNION
    SELECT player_id FROM v_sports_bets_enriched
    WHERE bet_date >= :start AND bet_date < :end
      AND (:country = 'All markets' OR country = :country)
);

-- 5. FTD count: first-ever approved deposit falls in reporting period
WITH first_deposit AS (
    SELECT player_id, MIN(transaction_date) AS ftd_date
    FROM transactions
    WHERE transaction_type = 'Deposit' AND transaction_status = 'Approved'
    GROUP BY player_id
)
SELECT COUNT(*) AS ftd_count
FROM first_deposit f
JOIN players p USING (player_id)
WHERE f.ftd_date >= :start AND f.ftd_date < :end
  AND (:country = 'All markets' OR p.country = :country);

-- 6. Observed FTD Conversion D30 by mature registration cohort
WITH first_deposit AS (
    SELECT player_id, MIN(transaction_date) AS ftd_date
    FROM transactions
    WHERE transaction_type = 'Deposit' AND transaction_status = 'Approved'
    GROUP BY player_id
), eligible AS (
    SELECT p.player_id, p.registration_date, f.ftd_date
    FROM players p LEFT JOIN first_deposit f USING (player_id)
    WHERE p.registration_date >= :start
      AND p.registration_date < :end
      AND p.registration_date <= DATETIME(:end, '-30 days')
      AND (:country = 'All markets' OR p.country = :country)
)
SELECT COUNT(*) AS eligible_registrations,
       SUM(ftd_date >= registration_date
           AND ftd_date < DATETIME(registration_date, '+30 days')) AS converted_d30,
       1.0 * SUM(ftd_date >= registration_date
                 AND ftd_date < DATETIME(registration_date, '+30 days'))
           / NULLIF(COUNT(*), 0) AS ftd_conversion_d30
FROM eligible;

-- 7. Average approved deposit transaction
SELECT SUM(amount) / NULLIF(COUNT(*), 0) AS average_deposit
FROM v_transactions_enriched
WHERE transaction_type = 'Deposit' AND transaction_status = 'Approved'
  AND transaction_date >= :start AND transaction_date < :end
  AND (:country = 'All markets' OR country = :country);

-- 8. Observed Retention D30: return on days 30–36 after first gaming activity.
-- :start/:end select the activation cohort; :end is also the reporting as-of boundary.
WITH activity AS (
    SELECT player_id, DATE(session_start) AS activity_date FROM sessions
    UNION
    SELECT player_id, DATE(bet_date) FROM sports_bets
), first_activity AS (
    SELECT player_id, MIN(activity_date) AS activation_date
    FROM activity GROUP BY player_id
), eligible AS (
    SELECT f.player_id, f.activation_date
    FROM first_activity f JOIN players p USING (player_id)
    WHERE f.activation_date >= DATE(:start) AND f.activation_date < DATE(:end)
      AND f.activation_date <= DATE(:end, '-37 days')
      AND (:country = 'All markets' OR p.country = :country)
), retained AS (
    SELECT DISTINCT e.player_id
    FROM eligible e JOIN activity a USING (player_id)
    WHERE a.activity_date >= DATE(e.activation_date, '+30 days')
      AND a.activity_date < DATE(e.activation_date, '+37 days')
)
SELECT COUNT(*) AS eligible_players,
       COUNT(r.player_id) AS retained_players,
       1.0 * COUNT(r.player_id) / NULLIF(COUNT(*), 0) AS retention_d30
FROM eligible e LEFT JOIN retained r USING (player_id);

-- 9–10. Observed Actual RTP and signed RTP variance by game.
-- Positive variance is player-favourable/lower operator margin; negative is operator-favourable.
SELECT game_name,
       SUM(total_bet_amount) AS bets,
       SUM(total_payout_amount) AS payouts,
       SUM(total_payout_amount) / NULLIF(SUM(total_bet_amount), 0) AS actual_rtp,
       SUM(total_bet_amount * theoretical_rtp)
           / NULLIF(SUM(total_bet_amount), 0) AS weighted_theoretical_rtp,
       SUM(total_payout_amount) / NULLIF(SUM(total_bet_amount), 0)
       - SUM(total_bet_amount * theoretical_rtp)
           / NULLIF(SUM(total_bet_amount), 0) AS rtp_variance
FROM v_sessions_enriched
WHERE session_start >= :start AND session_start < :end
  AND (:country = 'All markets' OR country = :country)
GROUP BY game_name;

-- 11–14. Latest model scores. These are predictions, not observed KPI.
SELECT player_id, predicted_ltv_90d, churn_probability,
       fraud_risk, rg_risk, model_confidence, model_version, scored_at
FROM v_player_scores
WHERE (:country = 'All markets' OR country = :country);
