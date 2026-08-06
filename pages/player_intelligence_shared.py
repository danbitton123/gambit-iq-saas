from __future__ import annotations

import pandas as pd

from queries.player_intelligence import player_base


SEGMENTS = [
    "All players", "VIP active", "VIP at risk", "New FTD", "Growing players",
    "Became inactive", "Potential bonus abuse", "RG risk", "High future value",
]

SEGMENT_ICONS = {
    "VIP active": "workspace_premium", "VIP at risk": "diamond", "New FTD": "person_add",
    "Growing players": "trending_up", "Became inactive": "person_off", "Potential bonus abuse": "confirmation_number",
    "RG risk": "health_and_safety", "High future value": "query_stats",
}


def prepare_players(ctx) -> pd.DataFrame:
    players = player_base.run(ctx)
    previous = player_base.run_previous(ctx)[["player_id", "sessions", "sports_bets", "casino_ggr", "sports_ggr"]]
    previous = previous.rename(columns={column: f"previous_{column}" for column in previous.columns if column != "player_id"})
    players = players.merge(previous, on="player_id", how="left").fillna({
        "previous_sessions": 0, "previous_sports_bets": 0, "previous_casino_ggr": 0, "previous_sports_ggr": 0,
    })
    players["period_ggr"] = players.casino_ggr + players.sports_ggr
    players["previous_ggr"] = players.previous_casino_ggr + players.previous_sports_ggr
    players["activity"] = players.sessions + players.sports_bets
    players["previous_activity"] = players.previous_sessions + players.previous_sports_bets
    players["recency_days"] = (ctx.end.normalize() - pd.to_datetime(players.last_activity).dt.normalize()).dt.days.fillna(999).clip(lower=0)
    monetary_cutoff = max(float(players.loc[players.period_ggr > 0, "period_ggr"].quantile(.70) or 0), 1)
    frequency_cutoff = max(float(players.loc[players.activity > 0, "activity"].quantile(.70) or 0), 1)
    players["rfm_segment"] = "At risk"
    players.loc[(players.recency_days <= 30) & (players.activity > 0), "rfm_segment"] = "Active"
    players.loc[(players.recency_days <= 14) & (players.activity >= frequency_cutoff), "rfm_segment"] = "Loyal"
    players.loc[(players.recency_days <= 7) & (players.activity >= frequency_cutoff) & (players.period_ggr >= monetary_cutoff), "rfm_segment"] = "Champion"
    players.loc[(players.recency_days > 60), "rfm_segment"] = "Dormant"
    players["VIP active"] = players.vip_level.isin(["Gold", "Platinum"]) & (players.activity > 0)
    players["VIP at risk"] = players.vip_level.isin(["Gold", "Platinum"]) & (players.churn_probability >= .70)
    ftd_date = pd.to_datetime(players.ftd_date)
    players["New FTD"] = ftd_date.between(ctx.start, ctx.end + pd.Timedelta(1, unit="D"), inclusive="left")
    players["Growing players"] = (players.period_ggr > players.previous_ggr * 1.25) & (players.previous_ggr > 0)
    players["Became inactive"] = (players.activity == 0) & (players.previous_activity > 0)
    deposit_cutoff = max(float(players.deposit_count.quantile(.85) or 0), 2)
    players["Potential bonus abuse"] = (players.deposit_count >= deposit_cutoff) & players.fraud_risk.between(.35, .55, inclusive="left")
    players["RG risk"] = players.rg_risk >= .55
    players["High future value"] = players.predicted_total_ltv_180d >= players.predicted_total_ltv_180d.quantile(.90)
    players["segment_tags"] = players.apply(lambda row: ", ".join(segment for segment in SEGMENTS[1:] if bool(row[segment])) or "Standard", axis=1)
    players["crm_eligible"] = (players.fraud_risk < .55) & (players.rg_risk < .55) & (players.kyc_status == "Verified")
    return players
