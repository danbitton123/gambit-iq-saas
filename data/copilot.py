from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, replace

import pandas as pd

from data.semantic_query import SemanticQueryEngine


@dataclass(frozen=True)
class CopilotResponse:
    intent: str
    title: str
    answer: str
    evidence: pd.DataFrame
    sources: tuple[str, ...]
    limitations: str
    confidence: float
    refused: bool = False
    chart: "CopilotChart | None" = None


@dataclass(frozen=True)
class CopilotChart:
    kind: str
    x: str
    y: tuple[str, ...]
    title: str
    explanation: str


@dataclass(frozen=True)
class ApprovedIntent:
    intent: str
    title: str
    patterns: tuple[str, ...]
    handler: str
    description: str


APPROVED_INTENTS = (
    ApprovedIntent("ngr_change", "NGR change drivers", ("ngr", "net gaming revenue", "revenu net", "revenue decrease", "revenue drop", "baisse.*revenu"), "_ngr_change", "Explain NGR movement versus the equivalent previous period."),
    ApprovedIntent("game_performance", "Underperforming games", ("underperforming game", "games.*perform", "jeu.*sous", "worst game", "rtp.*game", "performance.*jeu"), "_games", "Rank games using observed GGR, margin, volume and RTP variance."),
    ApprovedIntent("acquisition_budget", "Acquisition budget allocation", ("acquisition channel", "more budget", "budget.*channel", "canal.*budget", "roas", "source.*acquisition"), "_acquisition", "Compare governed predicted ROAS proxies and cohort quality."),
    ApprovedIntent("churn_risk", "Revenue at risk from churn", ("churn", "attrition", "inactive player", "revenu.*risque", "revenue.*risk"), "_churn", "Quantify predicted churn exposure using future-value estimates."),
    ApprovedIntent("vip_attention", "VIP players requiring attention", ("vip", "high value player", "joueur.*valeur", "player.*attention"), "_vip", "Prioritize anonymized VIP cases with safety guardrails."),
    ApprovedIntent("withdrawal_failures", "Withdrawal failure drivers", ("withdrawal fail", "failed withdrawal", "retrait.*[ée]chec", "withdrawal decline", "payment failure"), "_withdrawals", "Explain changes in failed withdrawals by payment method."),
    ApprovedIntent("priority_actions", "Five priority actions", ("five.*action", "5.*action", "most important action", "priority action", "actions.*today", "actions.*aujourd"), "_actions", "Rank governed Decision Engine alerts."),
    ApprovedIntent("casino_summary", "Casino performance summary", ("casino performance", "casino summary", "résumé.*casino", "performance.*casino", "how.*casino"), "_casino_summary", "Summarize casino revenue, RTP, activity and leading game."),
    ApprovedIntent("sportsbook_summary", "Sportsbook performance summary", ("sportsbook", "sports betting", "pari.*sport", "betting performance"), "_sportsbook", "Summarize handle, GGR, hold and event concentration."),
    ApprovedIntent("payments_summary", "Payments summary", ("deposit", "payment", "paiement", "dépôt", "cash flow"), "_payments", "Summarize deposits, withdrawals and approval rate."),
    ApprovedIntent("data_quality", "Data coverage and readiness", ("missing data", "data.*missing", "donnée.*manqu", "data quality", "qualité.*donnée", "coverage.*data"), "_data_quality", "Explain source coverage and model readiness for the active client scope."),
)

SUGGESTED_QUESTIONS = (
    "Why did NGR decrease versus the previous period?",
    "Which games are underperforming?",
    "Which acquisition channels should receive more budget?",
    "How much revenue is currently at risk from churn?",
    "Which VIP players require immediate attention?",
    "What caused the increase in withdrawal failures?",
    "What are today’s five most important actions?",
)

PAGE_DEFAULT_INTENTS = {
    "Command Center": "priority_actions", "AI Copilot": "priority_actions",
    "Player Intelligence": "vip_attention", "CRM Automation": "churn_risk",
    "Casino": "casino_summary", "Sportsbook": "sportsbook_summary",
    "Acquisition": "acquisition_budget", "Revenue & Finance": "ngr_change",
    "Risk & Compliance": "vip_attention", "Data Import Studio": "data_quality",
}

FOLLOW_UP_PATTERNS = (r"^why\??$", r"^pourquoi\??$", r"explain", r"explique", r"more detail", r"plus de détail", r"et pourquoi", r"what about", r"et pour")


def _num(value, default: float = 0.0) -> float:
    return default if value is None or pd.isna(value) else float(value)


def _money(value: float) -> str:
    sign = "−" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def _change(current: float, previous: float) -> float:
    return (current-previous)/abs(previous) if previous else 0.0


def _alias(player_id: str) -> str:
    return f"Player {hashlib.sha256(str(player_id).encode()).hexdigest()[:8].upper()}"


class GovernedCopilot:
    """Maps questions to an allow-list of parameterized analytical routines.

    User text is never interpolated into SQL. Only the global SQLContext
    parameters and fixed approved statements can reach the warehouse.
    """

    def __init__(self, ctx, alerts=()):
        self.ctx = ctx
        self.alerts = list(alerts)

    @property
    def scope(self) -> str:
        return self.ctx.period_label

    def ask(self, question: str, previous_intent: str | None = None, page_context: str | None = None) -> CopilotResponse:
        normalized = re.sub(r"\s+", " ", question.strip().lower())
        if len(normalized) < 4:
            return self._refusal("Please ask a complete business question about casino, sportsbook, players, acquisition, payments, risk or revenue.")
        if self._sensitive_request(normalized):
            return self._refusal("I cannot reveal direct player identifiers, names, contact details, credentials or raw personal data. I can provide anonymized operational cohorts instead.")
        intent = next((item for item in APPROVED_INTENTS if any(re.search(pattern, normalized) for pattern in item.patterns)), None)
        if intent is None and previous_intent and any(re.search(pattern, normalized) for pattern in FOLLOW_UP_PATTERNS):
            intent = next((item for item in APPROVED_INTENTS if item.intent == previous_intent), None)
        page_prompt = any(term in normalized for term in ("this page", "cette page", "this chart", "ce graphique", "these kpi", "ces kpi", "focus on", "important ici"))
        if intent is None and page_context and page_prompt:
            default_intent = PAGE_DEFAULT_INTENTS.get(page_context)
            intent = next((item for item in APPROVED_INTENTS if item.intent == default_intent), None)
        if intent is None:
            semantic = SemanticQueryEngine(self.ctx).answer(question)
            if semantic is not None:
                chart = CopilotChart(semantic.chart_kind,semantic.chart_x,semantic.chart_y,semantic.title.upper(),"Generated from the same governed evidence cited in this response.") if semantic.chart_x and semantic.chart_kind != "table" else None
                response = CopilotResponse("semantic_query",semantic.title,semantic.answer,semantic.evidence,semantic.sources,semantic.limitations,semantic.confidence,False,chart)
                return self._conversational_answer(question,response,page_context)
            intent = self._model_route(question, page_context)
        if intent is None:
            return self._refusal("I could not map this question to the governed casino data model. Ask about revenue, players, games, acquisition, payments, risk, sportsbook or data quality, and specify a breakdown such as country, channel, game or month.")
        response = self._with_chart(getattr(self, intent.handler)())
        return self._conversational_answer(question, response, page_context)

    @staticmethod
    def _model_route(question: str, page_context: str | None) -> ApprovedIntent | None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return None
        try:
            from openai import OpenAI
            catalogue = "\n".join(f"{item.intent}: {item.description}" for item in APPROVED_INTENTS)
            result = OpenAI(api_key=api_key, timeout=8.0, max_retries=1).responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-5.6"), store=False,
                instructions=("Classify the business question into exactly one approved intent ID from the catalogue. "
                              "Return only the ID. Return OUT_OF_SCOPE for unrelated, ambiguous or unsupported requests. "
                              "Never answer the question and never create a new intent."),
                input=f"Page: {page_context or 'unknown'}\nQuestion: {question}\nApproved catalogue:\n{catalogue}",
            )
            selected = (result.output_text or "").strip()
            return next((item for item in APPROVED_INTENTS if item.intent == selected), None)
        except Exception:
            return None

    @staticmethod
    def _with_chart(response: CopilotResponse) -> CopilotResponse:
        candidates = {
            "ngr_change": CopilotChart("bar","Driver",("Current","Previous"),"NGR DRIVERS · CURRENT VS PREVIOUS","Compares governed revenue components over equivalent periods."),
            "game_performance": CopilotChart("bar","Game",("GGR",),"GAMES REQUIRING REVIEW","Ranks the weakest observed game results in the active scope."),
            "acquisition_budget": CopilotChart("bar","Channel",("Predicted_ROAS",),"PREDICTED ROAS BY CHANNEL","Predicted proxy only; validate actual spend and incrementality before reallocating budget."),
            "churn_risk": CopilotChart("bar","Risk_band",("Value_at_risk",),"CHURN VALUE AT RISK","Probability-weighted future value grouped by predicted risk band."),
            "vip_attention": CopilotChart("bar","Player",("churn_probability_30d","fraud_risk","rg_risk"),"ANONYMIZED VIP RISK QUEUE","Compares modelled risks; player-protection signals override commercial actions."),
            "withdrawal_failures": CopilotChart("bar","Payment_method",("Failure_rate_current","Failure_rate_previous"),"WITHDRAWAL FAILURE RATE","Compares observed failure rates by method across equivalent periods."),
            "priority_actions": CopilotChart("bar","Signal",("Impact",),"PRIORITY ACTION IMPACT","Rule-specific estimates can overlap and are not additive accounting loss."),
            "casino_summary": CopilotChart("bar","Game",("GGR",),"CASINO GGR BY GAME","Observed GGR for games in the selected period and market."),
            "sportsbook_summary": CopilotChart("bar","Sport",("Handle","GGR"),"SPORTSBOOK PERFORMANCE BY SPORT","Observed settled handle and GGR; handle is not open liability."),
            "payments_summary": CopilotChart("bar","Payment_method",("Deposits","Withdrawals"),"PAYMENT FLOWS BY METHOD","Observed approved deposit and withdrawal value."),
            "data_quality": CopilotChart("bar","Dataset",("Rows",),"ACTIVE DATA COVERAGE","Row coverage in governed analytical tables for the selected scope."),
        }
        chart = candidates.get(response.intent)
        required = {chart.x, *chart.y} if chart else set()
        return replace(response, chart=chart) if chart and required <= set(response.evidence.columns) and not response.evidence.empty else response

    def _conversational_answer(self, question: str, response: CopilotResponse, page_context: str | None) -> CopilotResponse:
        """Optionally enrich a governed result; the model never receives SQL or raw identifiers."""
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or response.refused:
            return response
        try:
            from openai import OpenAI
            evidence = response.evidence.head(25).where(pd.notna(response.evidence.head(25)), None).to_dict(orient="records")
            client = OpenAI(api_key=api_key, timeout=8.0, max_retries=1)
            result = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-5.6"), store=False,
                instructions=("You are Gambit IQ, a concise senior iGaming analyst. Answer only from the supplied "
                              "governed analysis. Never invent values, players, causes or actions. Clearly distinguish "
                              "observed, estimated and predicted evidence. Mention uncertainty and keep the response under 170 words."),
                input=json.dumps({"question":question,"page":page_context,"scope":self.scope,"approved_answer":response.answer,
                                  "evidence":evidence,"limitations":response.limitations}, default=str),
            )
            narrative = (result.output_text or "").strip()
            if narrative:
                return CopilotResponse(response.intent,response.title,narrative,response.evidence,response.sources,
                                       response.limitations,response.confidence,response.refused,response.chart)
        except Exception:
            pass
        return response

    @staticmethod
    def _sensitive_request(question: str) -> bool:
        sensitive = ("email", "phone", "address", "password", "credential", "full name", "player id", "raw id", "nom complet", "adresse")
        return any(term in question for term in sensitive)

    def _source(self, *tables: str) -> tuple[str, ...]:
        return tuple(f"{table} · global scope: {self.scope}" for table in tables)

    def _refusal(self, reason: str) -> CopilotResponse:
        return CopilotResponse("refused", "Question not processed", reason, pd.DataFrame(), ("Approved intent catalogue",), "No warehouse query was executed.", 1.0, True)

    def _ngr_change(self) -> CopilotResponse:
        sql = """SELECT COALESCE(SUM(casino_ggr),0) casino_ggr,COALESCE(SUM(sports_ggr),0) sportsbook_ggr,
          COALESCE(SUM(payment_fees),0) fees,COALESCE(SUM(total_ggr),0) ggr FROM mart_executive_daily
          WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
          AND (:country='All markets' OR country=:country)"""
        current, previous = self.ctx.query(sql).iloc[0], self.ctx.previous_query(sql).iloc[0]
        rows = []
        for label, column in (("Casino GGR","casino_ggr"),("Sportsbook GGR","sportsbook_ggr"),("Payment fees","fees")):
            now, prior = _num(current[column]), _num(previous[column])
            rows.append((label, now, prior, now-prior, _change(now, prior)))
        evidence = pd.DataFrame(rows, columns=["Driver","Current","Previous","Absolute change","Relative change"])
        ggr, prior_ggr = _num(current.ggr), _num(previous.ggr)
        ngr = ggr-_num(current.fees)-max(ggr,0)*.16
        prior_ngr = prior_ggr-_num(previous.fees)-max(prior_ggr,0)*.16
        biggest = evidence.iloc[evidence["Absolute change"].abs().argmax()]
        direction = "decreased" if ngr < prior_ngr else "increased"
        answer = f"Estimated NGR {direction} by {_money(abs(ngr-prior_ngr))} ({_change(ngr,prior_ngr):+.1%}) versus the equivalent previous period. The largest measured driver was {biggest.Driver}, changing by {_money(biggest['Absolute change'])}."
        return CopilotResponse("ngr_change", "Estimated NGR movement", answer, evidence, self._source("mart_executive_daily"), "NGR uses explicit demo provisions of 6.5% bonuses and 9.5% taxes because observed bonus and tax ledgers are not connected.", .92)

    def _games(self) -> CopilotResponse:
        evidence = self.ctx.query("""SELECT game_name Game,provider Provider,SUM(ggr) GGR,SUM(bets) Bets,
          SUM(ggr)/NULLIF(SUM(bets),0) Margin,SUM(payouts)/NULLIF(SUM(bets),0) Actual_RTP,
          SUM(bets*theoretical_rtp)/NULLIF(SUM(bets),0) Theoretical_RTP,
          SUM(payouts)/NULLIF(SUM(bets),0)-SUM(bets*theoretical_rtp)/NULLIF(SUM(bets),0) RTP_variance
          FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
          AND (:country='All markets' OR country=:country) GROUP BY game_name,provider
          HAVING SUM(bets)>0 ORDER BY Margin ASC,GGR ASC LIMIT 5""")
        if evidence.empty:
            return CopilotResponse("game_performance", "Underperforming games", "No casino activity matches the active filters.", evidence, self._source("mart_game_performance_daily"), "No ranking is possible without settled bets.", .99)
        worst = evidence.iloc[0]
        answer = f"{worst.Game} is the weakest game in the selected scope: {_money(_num(worst.GGR))} GGR, {_num(worst.Margin):.2%} margin and {_num(worst.RTP_variance):+.2%} RTP variance versus theoretical. Review the ranked evidence before changing provider or game placement."
        return CopilotResponse("game_performance", "Games requiring review", answer, evidence, self._source("mart_game_performance_daily", "dim_game"), "Low margin can be normal over small samples; wager volume and statistical significance must be reviewed.", .94)

    def _acquisition(self) -> CopilotResponse:
        cost = "CASE p.channel WHEN 'Google' THEN 34 WHEN 'Meta' THEN 38 WHEN 'Organic' THEN 8 WHEN 'Affiliate Alpha' THEN 47 WHEN 'Affiliate Nova' THEN 61 WHEN 'Influencers' THEN 73 ELSE 40 END"
        evidence = self.ctx.query(f"""SELECT p.channel Channel,COUNT(*) Players,AVG({cost}) Estimated_CAC,
          AVG(v.remaining_ltv_90d) Predicted_remaining_LTV_90D,
          AVG(v.remaining_ltv_90d)/NULLIF(AVG({cost}),0) Predicted_ROAS,
          AVG(v.churn_probability_30d) Churn_risk
          FROM players p JOIN v_player_scores v USING(player_id)
          WHERE p.registration_date>=:start AND p.registration_date<:end
          AND (:country='All markets' OR p.country=:country) GROUP BY p.channel ORDER BY Predicted_ROAS DESC""")
        if evidence.empty:
            return CopilotResponse("acquisition_budget", "Acquisition budget", "No registration cohort matches the active filters.", evidence, self._source("players", "model_scores"), "No recommendation is possible without a cohort.", .99)
        best, worst = evidence.iloc[0], evidence.iloc[-1]
        answer = f"Prioritize investigation of {best.Channel}, with a predicted ROAS proxy of {_num(best.Predicted_ROAS):.2f}x. {worst.Channel} ranks last at {_num(worst.Predicted_ROAS):.2f}x. Validate actual media spend, incrementality and cohort maturity before reallocating budget."
        return CopilotResponse("acquisition_budget", "Budget allocation evidence", answer, evidence, self._source("players", "model_scores.remaining_ltv_90d"), "CAC is a governed demo channel-cost assumption; ROAS is predicted, not observed incremental return.", .79)

    def _churn(self) -> CopilotResponse:
        evidence = self.ctx.query("""SELECT CASE WHEN churn_probability_30d>=.75 THEN 'Critical ≥75%'
          WHEN churn_probability_30d>=.60 THEN 'High 60–75%' ELSE 'Watch 45–60%' END Risk_band,
          COUNT(*) Players,SUM(remaining_ltv_90d) Future_value,
          SUM(remaining_ltv_90d*churn_probability_30d) Value_at_risk,AVG(churn_probability_30d) Avg_risk
          FROM v_player_scores v WHERE churn_probability_30d>=.45
          AND (:country='All markets' OR country=:country) AND EXISTS(SELECT 1 FROM int_player_activity_daily a
          WHERE a.player_id=v.player_id AND a.activity_date>=DATE(:start) AND a.activity_date<DATE(:end))
          GROUP BY Risk_band ORDER BY Avg_risk DESC""")
        total = _num(evidence.Value_at_risk.sum()) if not evidence.empty else 0
        players = int(evidence.Players.sum()) if not evidence.empty else 0
        answer = f"Estimated 90-day revenue at risk from churn is {_money(total)} across {players:,} active players with at least 45% predicted 30-day churn risk. This is probability-weighted future value, not confirmed loss."
        return CopilotResponse("churn_risk", "Churn value at risk", answer, evidence, self._source("model_scores", "int_player_activity_daily"), "Campaign impact and revenue actually saved require randomized treatment/control outcomes and are not inferred here.", .86)

    def _vip(self) -> CopilotResponse:
        raw = self.ctx.query("""SELECT v.player_id,v.vip_level,v.remaining_ltv_90d,v.churn_probability_30d,
          v.fraud_risk,v.rg_risk,v.recommended_action FROM v_player_scores v
          WHERE v.vip_level IN ('Gold','Platinum') AND (:country='All markets' OR v.country=:country)
          AND EXISTS(SELECT 1 FROM int_player_activity_daily a WHERE a.player_id=v.player_id
          AND a.activity_date>=DATE(:start) AND a.activity_date<DATE(:end))
          ORDER BY MAX(v.churn_probability_30d,v.fraud_risk,v.rg_risk) DESC,v.remaining_ltv_90d DESC LIMIT 10""")
        evidence = raw.copy()
        if not evidence.empty:
            evidence["Player"] = evidence.player_id.map(_alias)
            evidence = evidence.drop(columns="player_id")[["Player","vip_level","remaining_ltv_90d","churn_probability_30d","fraud_risk","rg_risk","recommended_action"]]
        urgent = len(evidence[(evidence.churn_probability_30d>=.6)|(evidence.fraud_risk>=.55)|(evidence.rg_risk>=.55)]) if not evidence.empty else 0
        answer = f"{urgent} anonymized VIP cases in the top-ten review queue exceed a churn or safety threshold. Responsible Gaming and fraud review must take precedence over retention activity."
        return CopilotResponse("vip_attention", "VIP attention queue", answer, evidence, self._source("v_player_scores", "int_player_activity_daily"), "Player identifiers are irreversibly replaced with session-safe aliases in the answer. Human review is mandatory.", .91)

    def _withdrawals(self) -> CopilotResponse:
        sql = """SELECT payment_method Payment_method,COUNT(*) Attempts,
          SUM(transaction_status='Declined') Failed,
          1.0*SUM(transaction_status='Declined')/NULLIF(COUNT(*),0) Failure_rate
          FROM v_transactions_enriched WHERE transaction_type='Withdrawal'
          AND transaction_date>=:start AND transaction_date<:end
          AND (:country='All markets' OR country=:country) GROUP BY payment_method"""
        current = self.ctx.query(sql); previous = self.ctx.previous_query(sql)
        evidence = current.merge(previous, on="Payment_method", how="outer", suffixes=("_current","_previous")).fillna(0)
        evidence["Failure_change"] = evidence.Failure_rate_current-evidence.Failure_rate_previous
        evidence = evidence.sort_values("Failure_change", ascending=False)
        if evidence.empty:
            return CopilotResponse("withdrawal_failures", "Withdrawal failures", "No withdrawal attempts match the active filters.", evidence, self._source("v_transactions_enriched"), "No causal conclusion is possible.", .99)
        driver = evidence.iloc[0]
        answer = f"{driver.Payment_method} contributed the largest deterioration: failure rate changed from {_num(driver.Failure_rate_previous):.1%} to {_num(driver.Failure_rate_current):.1%} ({_num(driver.Failure_change):+.1%} points). This identifies correlation by method, not the processor root cause."
        return CopilotResponse("withdrawal_failures", "Withdrawal failure drivers", answer, evidence, self._source("v_transactions_enriched"), "Issuer response codes and processor incident logs are not available, so root cause remains provisional.", .89)

    def _actions(self) -> CopilotResponse:
        selected = self.alerts[:5]
        evidence = pd.DataFrame([{"Priority":a.priority,"Action":a.recommendation,"Owner":a.team,"Impact":a.financial_impact,"Confidence":a.confidence,"Signal":a.title} for a in selected])
        if not selected:
            return CopilotResponse("priority_actions", "Priority actions", "No governed alert is currently triggered for the active scope.", evidence, self._source("Decision Engine approved rules"), "Only governed triggered rules are ranked.", .98)
        answer = f"The five-action queue is led by {selected[0].title} for {selected[0].team}. Its estimated impact is {_money(selected[0].financial_impact)} with {selected[0].confidence:.0%} confidence. All actions require owner approval."
        return CopilotResponse("priority_actions", "Today’s priority actions", answer, evidence, self._source("Decision Engine", "mart_executive_daily", "model_scores"), "Financial impacts can overlap and must not be summed as accounting loss.", .93)

    def _casino_summary(self) -> CopilotResponse:
        evidence = self.ctx.query("""SELECT game_name Game,SUM(ggr) GGR,SUM(bets) Bets,SUM(sessions) Sessions,
          SUM(payouts)/NULLIF(SUM(bets),0) RTP,SUM(ggr)/NULLIF(SUM(bets),0) Margin
          FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
          AND (:country='All markets' OR country=:country) GROUP BY game_name ORDER BY GGR DESC""")
        if evidence.empty: return CopilotResponse("casino_summary","Casino summary","No casino activity matches the active filters.",evidence,self._source("mart_game_performance_daily"),"No data.",.99)
        answer = f"Casino generated {_money(evidence.GGR.sum())} GGR from {_money(evidence.Bets.sum())} settled bets. {evidence.iloc[0].Game} led GGR at {_money(_num(evidence.iloc[0].GGR))}; portfolio RTP was {_num((evidence.RTP*evidence.Bets).sum()/max(evidence.Bets.sum(),1)):.2%}."
        return CopilotResponse("casino_summary","Casino performance",answer,evidence,self._source("mart_game_performance_daily"),"Observed results can vary from theoretical RTP over finite samples.",.97)

    def _sportsbook(self) -> CopilotResponse:
        evidence = self.ctx.query("""SELECT sport Sport,SUM(stake) Handle,SUM(sportsbook_ggr) GGR,
          SUM(sportsbook_ggr)/NULLIF(SUM(stake),0) Hold,COUNT(*) Bets FROM v_sports_bets_enriched
          WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country)
          GROUP BY sport ORDER BY Handle DESC""")
        handle = _num(evidence.Handle.sum()) if not evidence.empty else 0; ggr = _num(evidence.GGR.sum()) if not evidence.empty else 0
        answer = f"Sportsbook settled {_money(handle)} handle and generated {_money(ggr)} GGR ({ggr/handle:.2%} hold)." if handle else "No sportsbook activity matches the active filters."
        return CopilotResponse("sportsbook_summary","Sportsbook performance",answer,evidence,self._source("v_sports_bets_enriched"),"Settled handle is not open event liability.",.97)

    def _payments(self) -> CopilotResponse:
        evidence = self.ctx.query("""SELECT payment_method Payment_method,COUNT(*) Transactions,SUM(amount) Volume,
          AVG(transaction_status='Approved') Approval_rate,
          SUM(CASE WHEN transaction_type='Deposit' AND transaction_status='Approved' THEN amount ELSE 0 END) Deposits,
          SUM(CASE WHEN transaction_type='Withdrawal' AND transaction_status='Approved' THEN amount ELSE 0 END) Withdrawals
          FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end
          AND (:country='All markets' OR country=:country) GROUP BY payment_method ORDER BY Volume DESC""")
        deposits = _num(evidence.Deposits.sum()) if not evidence.empty else 0; withdrawals = _num(evidence.Withdrawals.sum()) if not evidence.empty else 0
        approval = _num((evidence.Approval_rate*evidence.Transactions).sum()/max(evidence.Transactions.sum(),1)) if not evidence.empty else 0
        answer = f"Approved deposits were {_money(deposits)}, approved withdrawals {_money(withdrawals)}, and weighted payment approval was {approval:.1%}."
        return CopilotResponse("payments_summary","Payments performance",answer,evidence,self._source("v_transactions_enriched"),"Processor response codes and settlement timing are not available.",.96)

    def _data_quality(self) -> CopilotResponse:
        evidence = self.ctx.query("""SELECT 'Players' Dataset,COUNT(DISTINCT player_id) Rows FROM players
          WHERE (:country='All markets' OR country=:country)
          UNION ALL SELECT 'Casino sessions',COUNT(*) FROM v_sessions_enriched
          WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country)
          UNION ALL SELECT 'Sportsbook bets',COUNT(*) FROM v_sports_bets_enriched
          WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country)
          UNION ALL SELECT 'Transactions',COUNT(*) FROM v_transactions_enriched
          WHERE transaction_date>=:start AND transaction_date<:end AND (:country='All markets' OR country=:country)""")
        missing = evidence.loc[evidence.Rows.eq(0),"Dataset"].tolist()
        model_status = "available" if self.ctx.repo.model_available() else "unavailable"
        coverage = ", ".join(missing) if missing else "none of the four core analytical domains"
        answer = f"Core data coverage is present for {len(evidence)-len(missing)} of {len(evidence)} domains; missing coverage: {coverage}. Governed model outputs are {model_status}. A zero count can reflect the active market or period rather than an absent source file."
        return CopilotResponse("data_quality","Data coverage and readiness",answer,evidence,
                               self._source("players","v_sessions_enriched","v_sports_bets_enriched","v_transactions_enriched"),
                               "This checks analytical row coverage, not every source-column quality rule. Use Data Import Studio for field-level errors and duplicates.",.99)


def approved_catalog() -> pd.DataFrame:
    rows = [{"Intent":item.intent,"Approved analysis":item.title,"What it answers":item.description} for item in APPROVED_INTENTS]
    rows.append({"Intent":"semantic_query","Approved analysis":"Open governed data analysis","What it answers":"Flexible read-only aggregations across allow-listed business metrics and dimensions."})
    return pd.DataFrame(rows)
