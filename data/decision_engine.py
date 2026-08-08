from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


COST_SQL = "CASE p.channel WHEN 'Google' THEN 34 WHEN 'Meta' THEN 38 WHEN 'Organic' THEN 8 WHEN 'Affiliate Alpha' THEN 47 WHEN 'Affiliate Nova' THEN 61 WHEN 'Influencers' THEN 73 ELSE 40 END"

RULE_CATALOG = {
    "GGR_DROP": ("Unusual GGR decline", "Observed GGR", "Revenue & Finance", "GGR decreases by at least 10% versus the equivalent prior period."),
    "RTP_ANOMALY": ("Abnormal RTP variance", "Observed RTP", "Casino Operations", "A sufficiently active game's actual RTP differs from theoretical RTP by at least 2 percentage points."),
    "CAMPAIGN_LOSS": ("Unprofitable acquisition campaign", "Predicted ROAS Proxy 90D", "Growth", "A channel's predicted LTV Proxy divided by demo acquisition cost falls below 1.5x."),
    "SUPPLIER_DROP": ("Underperforming provider", "Observed provider GGR", "Casino Operations", "Provider GGR falls by at least 15% versus the equivalent prior period."),
    "WITHDRAWAL_SPIKE": ("Withdrawal increase", "Observed withdrawals", "Payments", "Approved withdrawals increase by at least 20% versus the equivalent prior period."),
    "CONVERSION_DROP": ("Conversion decline", "Observed period FTD rate", "Growth", "Period FTD / registrations decreases by at least 15% relative to the prior period."),
    "SPORTS_EXPOSURE": ("Excessive sportsbook exposure", "Observed event handle share", "Sportsbook Trading", "One event represents at least 35% of settled handle."),
    "REVENUE_CONCENTRATION": ("Excessive revenue concentration", "Observed player GGR share", "VIP & CRM", "The top ten players generate at least 25% of positive player GGR."),
    "FRAUD_SIGNAL": ("Potentially fraudulent behavior", "Predicted fraud risk", "Risk & Compliance", "Active players have a fraud-risk score of at least 55%."),
    "RG_SIGNAL": ("Sensitive Responsible Gaming behavior", "Predicted RG risk", "Player Protection", "Active players have an RG-risk score of at least 55%."),
}


@dataclass(frozen=True)
class DecisionAlert:
    rule_id: str
    title: str
    severity: str
    kpi: str
    current_value: str
    usual_value: str
    financial_impact: float
    impact_note: str
    probable_cause: str
    recommendation: str
    team: str
    effort: str
    priority: str
    confidence: float
    detected_at: str
    market: str
    period_start: str

    @property
    def workflow_id(self) -> str:
        """Stable workflow identity shared by country and all-market views."""
        return f"{self.rule_id}:{self.market}:{self.period_start}:{self.detected_at}"

    @property
    def revenue_potential(self) -> float:
        recovery = {"Critical": .45, "High": .32, "Medium": .20}.get(self.severity, .12)
        return max(self.financial_impact, 0) * recovery


def _number(value, default: float = 0.0) -> float:
    return default if value is None or pd.isna(value) else float(value)


def _ratio(current: float, usual: float) -> float:
    return (current - usual) / abs(usual) if usual else 0.0


def _severity(magnitude: float, high: float, critical: float) -> str:
    return "Critical" if magnitude >= critical else "High" if magnitude >= high else "Medium"


_SEVERITY_RANK = {"Critical": 0, "High": 1, "Medium": 2}


def top_alerts(alerts: list[DecisionAlert], teams: set[str] | None = None, limit: int = 6) -> list[DecisionAlert]:
    """One card per distinct rule (its worst-affected market), not one per market — otherwise a
    single rule triggering in every country would crowd out every other signal when "All markets"
    is selected. Optionally scoped to a set of team names so every page can show only the alerts
    its own owner is responsible for, using the exact same selection Command Center uses for its
    own cross-team top 6 — one selection rule, everywhere it's used."""
    scoped = [alert for alert in alerts if teams is None or alert.team in teams]
    worst_per_rule: dict[str, DecisionAlert] = {}
    for alert in scoped:
        current = worst_per_rule.get(alert.rule_id)
        rank = (_SEVERITY_RANK.get(alert.severity, 3), -alert.financial_impact)
        if current is None or rank < (_SEVERITY_RANK.get(current.severity, 3), -current.financial_impact):
            worst_per_rule[alert.rule_id] = alert
    return sorted(worst_per_rule.values(), key=lambda alert: (_SEVERITY_RANK.get(alert.severity, 3), -alert.financial_impact))[:limit]


class DecisionEngine:
    """Evaluates deterministic, auditable rules against the governed SQL context."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.detected_at = f"{ctx.end:%d %b %Y}"

    def evaluate(self) -> list[DecisionAlert]:
        if self.ctx.country == "All markets":
            from data.repository import SQLContext
            alerts = []
            for country in self.ctx.repo.countries():
                country_ctx = SQLContext(self.ctx.repo, self.ctx.start, self.ctx.end, country)
                alerts.extend(DecisionEngine(country_ctx)._evaluate_scope())
            return self._sorted(alerts)
        return self._evaluate_scope()

    def _evaluate_scope(self) -> list[DecisionAlert]:
        alerts: list[DecisionAlert] = []
        alerts.extend(self._revenue_and_payments())
        alerts.extend(self._casino())
        alerts.extend(self._acquisition())
        alerts.extend(self._sportsbook())
        alerts.extend(self._concentration())
        alerts.extend(self._player_risk())
        return self._sorted(alerts)

    @staticmethod
    def _sorted(alerts: list[DecisionAlert]) -> list[DecisionAlert]:
        order = {"Critical": 0, "High": 1, "Medium": 2}
        return sorted(alerts, key=lambda alert: (order[alert.severity], -alert.financial_impact, alert.market, alert.rule_id))

    def _alert(self, rule_id: str, severity: str, current: str, usual: str, impact: float,
               impact_note: str, cause: str, recommendation: str, effort: str, confidence: float) -> DecisionAlert:
        title, kpi, team, _ = RULE_CATALOG[rule_id]
        priority = "P0" if severity == "Critical" else "P1" if severity == "High" else "P2"
        return DecisionAlert(rule_id, title, severity, kpi, current, usual, impact, impact_note, cause,
                             recommendation, team, effort, priority, confidence, self.detected_at,
                             self.ctx.country, f"{self.ctx.start:%d %b %Y}")

    def _revenue_and_payments(self) -> list[DecisionAlert]:
        sql = """SELECT COALESCE(SUM(total_ggr),0) ggr,COALESCE(SUM(withdrawals),0) withdrawals,
          COALESCE(SUM(deposits),0) deposits FROM mart_executive_daily
          WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
          AND (:country='All markets' OR country=:country)"""
        now, prior = self.ctx.query(sql).iloc[0], self.ctx.previous_query(sql).iloc[0]
        output = []
        ggr_change = _ratio(_number(now.ggr), _number(prior.ggr))
        if ggr_change <= -.10:
            output.append(self._alert("GGR_DROP", _severity(-ggr_change, .18, .30), f"{ggr_change:+.1%}",
                "Prior-period baseline", max(_number(prior.ggr)-_number(now.ggr), 0), "Observed GGR gap",
                "Lower wager volume, weaker hold, or a mix shift toward lower-margin products.",
                "Decompose the gap by product, market and top contributors; assign owners to the largest negative drivers.", "Medium", .94))
        withdrawal_change = _ratio(_number(now.withdrawals), _number(prior.withdrawals))
        if withdrawal_change >= .20:
            output.append(self._alert("WITHDRAWAL_SPIKE", _severity(withdrawal_change, .35, .60), f"{withdrawal_change:+.1%}",
                f"${_number(prior.withdrawals):,.0f} prior", max(_number(now.withdrawals)-_number(prior.withdrawals), 0), "Excess cash outflow; not revenue loss",
                "Higher player wins, VIP cash-out activity, or a change in payment behavior.",
                "Review withdrawal concentration, payment methods and liquidity coverage before changing controls.", "Low", .96))
        return output

    def _casino(self) -> list[DecisionAlert]:
        output = []
        game = self.ctx.query("""SELECT game_name,provider,SUM(bets) bets,SUM(payouts)/NULLIF(SUM(bets),0) actual_rtp,
          SUM(bets*theoretical_rtp)/NULLIF(SUM(bets),0) expected_rtp
          FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
          AND (:country='All markets' OR country=:country) GROUP BY game_name,provider HAVING SUM(bets)>=10000
          ORDER BY ABS(actual_rtp-expected_rtp) DESC LIMIT 1""")
        if not game.empty:
            row = game.iloc[0]; variance = abs(_number(row.actual_rtp)-_number(row.expected_rtp))
            if variance >= .02:
                output.append(self._alert("RTP_ANOMALY", _severity(variance, .035, .05), f"{_number(row.actual_rtp):.2%}",
                    f"{_number(row.expected_rtp):.2%} theoretical", variance*_number(row.bets), "Wager value affected by RTP variance",
                    f"{row.game_name} ({row.provider}) has the largest statistically material variance in the filtered scope.",
                    "Validate settlements, game configuration and sample significance with the provider before escalation.", "Medium", .91))
        provider_sql = """SELECT provider,SUM(ggr) ggr FROM mart_game_performance_daily
          WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
          AND (:country='All markets' OR country=:country) GROUP BY provider"""
        current = self.ctx.query(provider_sql); prior = self.ctx.previous_query(provider_sql)
        providers = current.merge(prior, on="provider", suffixes=("_current", "_usual"))
        if not providers.empty:
            providers["change"] = (providers.ggr_current-providers.ggr_usual)/providers.ggr_usual.abs().replace(0, pd.NA)
            providers = providers.dropna(subset=["change"]).sort_values("change")
            if not providers.empty and providers.iloc[0].change <= -.15:
                row = providers.iloc[0]; decline = -float(row.change)
                output.append(self._alert("SUPPLIER_DROP", _severity(decline, .25, .40), f"{float(row.change):+.1%}",
                    f"${_number(row.ggr_usual):,.0f} prior GGR", max(_number(row.ggr_usual)-_number(row.ggr_current), 0), "Observed provider GGR gap",
                    f"{row.provider} lost the most momentum, potentially from traffic mix, game availability or payout variance.",
                    "Compare game-level volume and RTP, then open a provider review for the largest verified driver.", "Medium", .88))
        return output

    def _acquisition(self) -> list[DecisionAlert]:
        output = []
        campaign = self.ctx.query(f"""SELECT p.channel,COUNT(*) players,SUM({COST_SQL}) cost,
          SUM(v.predicted_ltv_90d) predicted_value,SUM(v.predicted_ltv_90d)/NULLIF(SUM({COST_SQL}),0) roas
          FROM players p JOIN v_player_scores v USING(player_id) WHERE p.registration_date>=:start AND p.registration_date<:end
          AND (:country='All markets' OR p.country=:country) GROUP BY p.channel ORDER BY roas LIMIT 1""")
        if not campaign.empty and _number(campaign.iloc[0].roas, 99) < 1.5:
            row = campaign.iloc[0]; roas = _number(row.roas)
            output.append(self._alert("CAMPAIGN_LOSS", "Critical" if roas < 1 else "High", f"{roas:.2f}x",
                "1.50x minimum", max(_number(row.cost)-_number(row.predicted_value), 0), "Predicted value shortfall versus demo cost",
                f"{row.channel} combines the weakest predicted LTV Proxy with its estimated channel acquisition cost.",
                "Validate actual media spend and cohort maturity, then pause or redesign the weakest placements.", "Medium", .78))
        conversion_sql = """SELECT SUM(ftd) ftd,SUM(registrations) registrations,
          1.0*SUM(ftd)/NULLIF(SUM(registrations),0) conversion FROM mart_acquisition_daily
          WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
          AND (:country='All markets' OR country=:country)"""
        now, prior = self.ctx.query(conversion_sql).iloc[0], self.ctx.previous_query(conversion_sql).iloc[0]
        decline = -_ratio(_number(now.conversion), _number(prior.conversion))
        if decline >= .15:
            avg_deposit = self.ctx.scalar("""SELECT AVG(amount) FROM v_transactions_enriched WHERE transaction_type='Deposit'
              AND transaction_status='Approved' AND transaction_date>=:start AND transaction_date<:end
              AND (:country='All markets' OR country=:country)""") or 0
            missing_ftd = max(_number(now.registrations)*_number(prior.conversion)-_number(now.ftd), 0)
            output.append(self._alert("CONVERSION_DROP", _severity(decline, .25, .40), f"{_number(now.conversion):.1%}",
                f"{_number(prior.conversion):.1%} prior", missing_ftd*float(avg_deposit), "Estimated missing first-deposit value",
                "Registration mix, KYC friction or payment acceptance may be reducing first-deposit completion.",
                "Break down the funnel by source, KYC status and payment method; repair the largest verified drop-off.", "Medium", .90))
        return output

    def _sportsbook(self) -> list[DecisionAlert]:
        events = self.ctx.query("""WITH e AS (SELECT event_name,SUM(stake) handle FROM v_sports_bets_enriched
          WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY event_name)
          SELECT event_name,handle,handle/(SELECT NULLIF(SUM(handle),0) FROM e) share FROM e ORDER BY handle DESC LIMIT 1""")
        if events.empty or _number(events.iloc[0].share) < .35:
            return []
        row = events.iloc[0]; share = _number(row.share)
        return [self._alert("SPORTS_EXPOSURE", _severity(share, .45, .60), f"{share:.1%} of handle", "35.0% limit",
            _number(row.handle)*max(share-.35, 0), "Concentrated settled handle above threshold",
            f"{row.event_name} concentrates an unusually large portion of handle in the selected scope.",
            "Review limits, bettor concentration and market liabilities with Trading; do not treat settled handle as open liability.", "Low", .97)]

    def _concentration(self) -> list[DecisionAlert]:
        concentration = self.ctx.query("""WITH g AS (SELECT player_id,SUM(ggr) ggr FROM (
          SELECT player_id,SUM(casino_ggr) ggr FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end
            AND (:country='All markets' OR country=:country) GROUP BY player_id
          UNION ALL SELECT player_id,SUM(sportsbook_ggr) FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end
            AND (:country='All markets' OR country=:country) GROUP BY player_id) GROUP BY player_id), ranked AS (
          SELECT MAX(ggr,0) positive_ggr,ROW_NUMBER() OVER(ORDER BY ggr DESC) rank FROM g)
          SELECT SUM(CASE WHEN rank<=10 THEN positive_ggr ELSE 0 END) top_ggr,SUM(positive_ggr) total_ggr,
          SUM(CASE WHEN rank<=10 THEN positive_ggr ELSE 0 END)/NULLIF(SUM(positive_ggr),0) share FROM ranked""")
        if concentration.empty or _number(concentration.iloc[0].share) < .25:
            return []
        row = concentration.iloc[0]; share = _number(row.share)
        return [self._alert("REVENUE_CONCENTRATION", _severity(share, .35, .50), f"{share:.1%} top-10 share", "25.0% threshold",
            _number(row.top_ggr)*max(share-.25, 0), "Revenue concentration above threshold",
            "A small high-value cohort contributes a disproportionate share of positive observed GGR.",
            "Create a monitored VIP continuity plan while preserving RG and affordability controls.", "Medium", .95)]

    def _player_risk(self) -> list[DecisionAlert]:
        sql = """SELECT COUNT(*) active,SUM(fraud_risk>=.55) fraud_cases,SUM(rg_risk>=.55) rg_cases,
          SUM(CASE WHEN fraud_risk>=.55 THEN predicted_ltv_90d*fraud_risk ELSE 0 END) fraud_impact,
          AVG(CASE WHEN fraud_risk>=.55 THEN model_confidence END) fraud_confidence,
          AVG(CASE WHEN rg_risk>=.55 THEN model_confidence END) rg_confidence
          FROM v_player_scores v WHERE (:country='All markets' OR country=:country) AND EXISTS (
          SELECT 1 FROM int_player_activity_daily a WHERE a.player_id=v.player_id
          AND a.activity_date>=DATE(:start) AND a.activity_date<DATE(:end))"""
        row = self.ctx.query(sql).iloc[0]; output = []
        fraud_cases, rg_cases, active = _number(row.fraud_cases), _number(row.rg_cases), max(_number(row.active), 1)
        if fraud_cases:
            rate = fraud_cases/active
            output.append(self._alert("FRAUD_SIGNAL", _severity(rate, .08, .15), f"{int(fraud_cases):,} active players",
                "55% score threshold", _number(row.fraud_impact), "Predicted LTV Proxy weighted by fraud risk",
                "Transaction and behavioral features place these accounts above the manual-review threshold.",
                "Route cases to Risk for evidence review; suppress CRM actions until cleared.", "High", _number(row.fraud_confidence, .70)))
        if rg_cases:
            rate = rg_cases/active
            output.append(self._alert("RG_SIGNAL", _severity(rate, .08, .15), f"{int(rg_cases):,} active players",
                "55% score threshold", 0, "Player-safety impact is intentionally not monetized",
                "Session intensity, deposits or behavioral features place these players above the RG review threshold.",
                "Prioritize human player-protection review and apply local policy; suppress commercial targeting.", "High", _number(row.rg_confidence, .70)))
        return output
