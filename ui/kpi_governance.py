from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KPIInfo:
    definition: str
    formula: str
    source: str
    status: str


KPI_REGISTRY: dict[str, KPIInfo] = {
    "Observed Total GGR": KPIInfo("Gaming revenue retained before direct deductions.", "Casino bets − payouts + sportsbook stakes − payouts", "mart_executive_daily", "Observed"),
    "Observed Casino GGR": KPIInfo("Casino revenue retained before direct deductions.", "Settled casino bets − settled casino payouts", "mart_game_performance_daily", "Observed"),
    "Observed Sportsbook GGR": KPIInfo("Sportsbook revenue retained before direct deductions.", "Settled stakes − settled payouts", "v_sports_bets_enriched", "Observed"),
    "Estimated NGR": KPIInfo("Estimated gaming revenue after the deductions available in the MVP.", "GGR − processing fees − 6.5% bonus provision − 9.5% tax provision", "Gaming facts + v_transactions_enriched + demo provisions", "Estimated"),
    "Observed Active Players": KPIInfo("Unique players with at least one settled gaming event.", "COUNT(DISTINCT player_id) across casino and sportsbook", "int_player_activity_daily / gaming facts", "Observed"),
    "Observed Lifetime GGR": KPIInfo("Observed casino and sportsbook GGR accumulated across the full available history for players in the selected market.", "Lifetime casino GGR + lifetime sportsbook GGR", "sessions + sports_bets", "Observed"),
    "Observed Total Bets": KPIInfo("Settled casino wager value.", "SUM(total_bet_amount)", "mart_game_performance_daily", "Observed"),
    "Observed GGR Margin": KPIInfo("Share of settled casino wagers retained as GGR.", "SUM(GGR) / SUM(bets)", "mart_game_performance_daily", "Observed"),
    "Observed Actual RTP": KPIInfo("Share of settled casino wagers returned to players.", "SUM(payouts) / SUM(bets)", "mart_game_performance_daily", "Observed"),
    "Observed Active Games": KPIInfo("Games with at least one settled session.", "COUNT(DISTINCT game_id)", "mart_game_performance_daily", "Observed"),
    "Observed Handle": KPIInfo("Total settled sportsbook stake value.", "SUM(stake)", "v_sports_bets_enriched", "Observed"),
    "Observed Hold": KPIInfo("Share of settled sportsbook handle retained as GGR.", "SUM(sportsbook_ggr) / SUM(stake)", "v_sports_bets_enriched", "Observed"),
    "Observed Blended Hold": KPIInfo("Share of settled casino and sportsbook wagers retained as GGR.", "Total observed GGR / total settled wagers", "mart_executive_daily", "Observed"),
    "Observed Realized Downside": KPIInfo("Absolute losses on settled bets with negative operator GGR; not open exposure.", "SUM(ABS(sportsbook_ggr)) WHERE sportsbook_ggr < 0", "v_sports_bets_enriched", "Observed"),
    "Observed Live Bets": KPIInfo("Settled bets placed in-play.", "SUM(is_live)", "v_sports_bets_enriched", "Observed"),
    "Observed FTD": KPIInfo("Players whose first-ever approved deposit falls in the reporting period.", "COUNT(DISTINCT player_id WHERE first_deposit_date in period)", "transactions", "Observed"),
    "Observed FTD Conversion D30": KPIInfo("Share of mature registrations making their first approved deposit within 30 days.", "Converted eligible registrations / registrations with a complete 30-day window", "players + transactions", "Observed"),
    "Estimated CAC": KPIInfo("Average demo acquisition cost assigned by channel.", "AVG(channel cost assumption)", "players.channel + demo cost mapping", "Estimated"),
    "Predicted ROAS Proxy 90D": KPIInfo("Predicted 90-day GGR proxy relative to estimated acquisition cost.", "Predicted LTV proxy 90D / estimated CAC", "model_scores + demo cost mapping", "Predicted"),
    "Predicted LTV Proxy 90D": KPIInfo("Modelled 90-day positive GGR proxy; not true net lifetime value.", "Model prediction extrapolated from future positive GGR", "model_scores.predicted_ltv_90d", "Predicted"),
    "Predicted Churn-Risk Players": KPIInfo("Active players with predicted churn probability of at least 70%.", "COUNT(players WHERE churn_probability ≥ 0.70)", "model_scores + filtered activity", "Predicted"),
    "Estimated Risk Exposure": KPIInfo("Lifetime GGR proxy linked to active accounts above fraud or RG review thresholds.", "SUM(MAX(lifetime_ggr, 0)) for flagged active accounts", "model_scores + filtered activity", "Estimated"),
    "Predicted High Churn Risk": KPIInfo("Active players with predicted churn probability of at least 70%.", "COUNT(players WHERE churn_probability ≥ 0.70)", "model_scores + filtered activity", "Predicted"),
    "Predicted VIP Candidates": KPIInfo("Active non-Platinum players above the demo value threshold.", "COUNT(players WHERE LTV proxy ≥ threshold)", "model_scores + players", "Predicted"),
    "Observed Retention D30": KPIInfo("Activated players returning on days 30–36 after first gaming activity.", "Retained eligible players / players with a complete 37-day window", "sessions + sports_bets", "Observed"),
    "Predicted High Fraud-Risk Rate": KPIInfo("Share of eligible players at or above the fraud-review threshold.", "AVG(fraud_risk ≥ 0.55)", "model_scores", "Predicted"),
    "Predicted Targetable Players": KPIInfo("Active players below both fraud and responsible-gaming review thresholds.", "COUNT(fraud_risk < 0.55 AND rg_risk < 0.55)", "model_scores + filtered activity", "Predicted"),
    "Estimated Campaign Opportunity": KPIInfo("Illustrative value opportunity for eligible recommended actions.", "8% × predicted LTV proxy 90D", "model_scores + demo response assumption", "Estimated"),
    "Estimated Uplift Assumption": KPIInfo("Illustrative uplift used by the CRM demo scenario.", "Fixed demo assumption: 23.6%", "Scenario assumption", "Estimated"),
    "Observed Bonus Efficiency": KPIInfo("Revenue generated per unit of bonus cost.", "Incremental observed revenue / observed bonus cost", "Bonus and experiment ledgers not connected", "Observed — unavailable"),
    "Predicted Risk Suppressions": KPIInfo("Active players excluded from campaigns by model guardrails.", "COUNT(fraud_risk ≥ 0.55 OR rg_risk ≥ 0.55)", "model_scores + filtered activity", "Predicted"),
    "Observed Deposits": KPIInfo("Value of approved deposit transactions.", "SUM(amount) for approved deposits", "v_transactions_enriched", "Observed"),
    "Observed Withdrawals": KPIInfo("Value of approved withdrawal transactions.", "SUM(amount) for approved withdrawals", "v_transactions_enriched", "Observed"),
    "Observed Net Cash Flow": KPIInfo("Approved deposits less approved withdrawals.", "Approved deposits − approved withdrawals", "v_transactions_enriched", "Observed"),
    "Observed Payment Approval Rate": KPIInfo("Share of payment transactions approved.", "Approved transactions / all payment transactions", "v_transactions_enriched", "Observed"),
    "Predicted Active Accounts Scored": KPIInfo("Active accounts covered by the current model scoring snapshot.", "COUNT(active players with model score)", "model_scores + filtered activity", "Predicted"),
    "Predicted High-Risk Cases": KPIInfo("Active accounts above fraud or RG manual-review thresholds.", "COUNT(fraud_risk ≥ 0.55 OR rg_risk ≥ 0.55)", "model_scores + filtered activity", "Predicted"),
    "Estimated Fraud Exposure": KPIInfo("Lifetime GGR proxy linked to active accounts above the fraud threshold; not prevented loss.", "SUM(MAX(lifetime_ggr, 0)) for flagged accounts", "model_scores", "Estimated"),
    "Predicted Fraud Reviews": KPIInfo("Active accounts above the fraud manual-review threshold.", "COUNT(fraud_risk ≥ 0.55)", "model_scores + filtered activity", "Predicted"),
    "Predicted RG Interventions": KPIInfo("Active accounts above the player-protection review threshold.", "COUNT(rg_risk ≥ 0.55)", "model_scores + filtered activity", "Predicted"),
    "Estimated Run-rate GGR 30D": KPIInfo("Thirty-day GGR run-rate extrapolated from the selected period.", "Selected-period GGR / selected days × 30", "Filtered casino and sportsbook GGR", "Estimated"),
    "Predicted Value at Risk": KPIInfo("Predicted LTV proxy attached to active players above the churn threshold.", "SUM(LTV proxy) WHERE churn_probability ≥ 0.70", "model_scores + filtered activity", "Predicted"),
    "Estimated Modelled Opportunities": KPIInfo("Illustrative value opportunity for eligible high-value players.", "8% × predicted LTV proxy 90D", "model_scores + demo response assumption", "Estimated"),
    "Predicted Model Confidence": KPIInfo("Average confidence stored with active-player predictions.", "AVG(model_confidence)", "model_scores", "Predicted"),
    "Observed Decision Mode": KPIInfo("Execution policy applied to AI recommendations.", "Human approval required before action", "Application governance", "Observed"),
    "Observed Active Alerts": KPIInfo("Governed decision rules currently breaching their operational threshold.", "COUNT(triggered rules)", "Decision Engine governed SQL rules", "Observed / model-assisted"),
    "Observed Critical Alerts": KPIInfo("Triggered alerts classified at the highest configured severity.", "COUNT(triggered rules WHERE severity = Critical)", "Decision Engine governed SQL rules", "Observed / model-assisted"),
    "Estimated Alert Impact": KPIInfo("Decision-support estimate attached to active alerts; values can overlap and are not additive accounting loss.", "SUM(rule-specific financial impact estimates)", "Observed facts + explicit rule assumptions", "Estimated"),
    "Estimated Recovery Potential": KPIInfo("Severity-adjusted portion of alert impact potentially addressable after investigation.", "Alert impact × configured severity recovery factor", "Decision Engine rule assumptions", "Estimated"),
    "Observed Reviewed Decisions": KPIInfo("Alerts marked reviewed or resolved in the current action register.", "COUNT(status IN Reviewed, Resolved)", "Decision Engine session action register", "Observed workflow status"),
    "Predicted Churn Probability": KPIInfo("Estimated probability of no qualifying activity in the model outcome window.", "Calibrated classifier probability", "model_scores.churn_probability", "Predicted"),
    "Predicted Fraud Risk": KPIInfo("Estimated probability proxy used to prioritize fraud review.", "Calibrated classifier probability", "model_scores.fraud_risk", "Predicted"),
    "Predicted RG Risk": KPIInfo("Estimated probability proxy used to prioritize player-protection review.", "Calibrated classifier probability", "model_scores.rg_risk", "Predicted"),
    "Predicted Model Confidence Detail": KPIInfo("Confidence stored for the selected player's score set.", "Model confidence output", "model_scores.model_confidence", "Predicted"),
}


def kpi_help(label: str, period: str, updated_at: str) -> str:
    info = KPI_REGISTRY.get(label)
    if info is None:
        raise KeyError(f"KPI governance metadata is missing for: {label}")
    return (
        f"Definition: {info.definition}\n\n"
        f"Formula: {info.formula}\n\n"
        f"Source: {info.source}\n\n"
        f"Period: {period}\n\n"
        f"Status: {info.status}\n\n"
        f"Last updated: {updated_at}"
    )
