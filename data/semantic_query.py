from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import pandas as pd

from data.errors import DataConnectionError,SQLQueryError


@dataclass(frozen=True)
class Metric:
    label: str
    expression: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class Dataset:
    table: str
    date_field: str | None
    dimensions: dict[str, str]
    metrics: dict[str, Metric]
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class QueryPlan:
    dataset: str
    dimensions: tuple[str, ...]
    metrics: tuple[str, ...]
    order_metric: str
    order_direction: str
    limit: int
    chart_type: str


@dataclass(frozen=True)
class SemanticResult:
    title: str
    answer: str
    evidence: pd.DataFrame
    sources: tuple[str, ...]
    limitations: str
    confidence: float
    chart_kind: str
    chart_x: str
    chart_y: tuple[str, ...]


DATASETS: dict[str, Dataset] = {
    "executive": Dataset("mart_executive_daily", "metric_date", {"country":"country","day":"DATE(metric_date)","week":"STRFTIME('%Y-W%W',metric_date)","month":"STRFTIME('%Y-%m',metric_date)"}, {
        "ggr": Metric("Observed GGR","SUM(total_ggr)",("revenue","revenu","ggr","gaming revenue")),
        "estimated_ngr": Metric("Estimated NGR","SUM(estimated_ngr)",("ngr","net gaming revenue","revenu net")),
        "casino_ggr": Metric("Observed Casino GGR","SUM(casino_ggr)",("casino revenue","casino ggr")),
        "sports_ggr": Metric("Observed Sportsbook GGR","SUM(sports_ggr)",("sports revenue","sportsbook ggr")),
        "wagers": Metric("Observed Wagers","SUM(total_wagers)",("wager","mise","handle")),
        "deposits": Metric("Observed Deposits","SUM(deposits)",("deposit","dépôt")),
        "withdrawals": Metric("Observed Withdrawals","SUM(withdrawals)",("withdrawal","retrait")),
        "margin": Metric("Observed GGR Margin","SUM(total_ggr)/NULLIF(SUM(total_wagers),0)",("margin","marge","hold")),
    }, ("executive","overall","global","country","market","revenue","revenu","ggr","ngr")),
    "casino": Dataset("mart_game_performance_daily", "metric_date", {"country":"country","game":"game_name","provider":"provider","game_family":"game_family","day":"DATE(metric_date)","month":"STRFTIME('%Y-%m',metric_date)"}, {
        "ggr": Metric("Observed Casino GGR","SUM(ggr)",("revenue","revenu","ggr")), "bets":Metric("Observed Bets","SUM(bets)",("bets","mises","wagers")),
        "sessions":Metric("Observed Sessions","SUM(sessions)",("session",)), "players":Metric("Observed Active Players","SUM(active_players)",("player","joueur")),
        "rtp":Metric("Observed Actual RTP","SUM(payouts)/NULLIF(SUM(bets),0)",("rtp",)), "margin":Metric("Observed GGR Margin","SUM(ggr)/NULLIF(SUM(bets),0)",("margin","marge")),
    }, ("casino","game","jeu","provider","fournisseur","rtp")),
    "sportsbook": Dataset("v_sports_bets_enriched", "bet_date", {"country":"country","sport":"sport","event":"event_name","channel":"channel","vip_level":"vip_level","day":"DATE(bet_date)","month":"STRFTIME('%Y-%m',bet_date)"}, {
        "ggr":Metric("Observed Sportsbook GGR","SUM(sportsbook_ggr)",("revenue","revenu","ggr")), "handle":Metric("Observed Handle","SUM(stake)",("handle","stake","mise","wager")),
        "payout":Metric("Observed Payout","SUM(payout)",("payout","gain")), "bets":Metric("Observed Bets","COUNT(*)",("bet","pari")),
        "hold":Metric("Observed Hold","SUM(sportsbook_ggr)/NULLIF(SUM(stake),0)",("hold","margin","marge")),
    }, ("sportsbook","sport","betting","pari","event","événement")),
    "payments": Dataset("v_transactions_enriched", "transaction_date", {"country":"country","payment_method":"payment_method","transaction_type":"transaction_type","status":"transaction_status","channel":"channel","vip_level":"vip_level","day":"DATE(transaction_date)","month":"STRFTIME('%Y-%m',transaction_date)"}, {
        "volume":Metric("Observed Transaction Volume","SUM(amount)",("volume","amount","montant")), "transactions":Metric("Observed Transactions","COUNT(*)",("transaction",)),
        "approval_rate":Metric("Observed Approval Rate","AVG(transaction_status='Approved')",("approval","approved","acceptation")),
        "deposits":Metric("Observed Approved Deposits","SUM(CASE WHEN transaction_type='Deposit' AND transaction_status='Approved' THEN amount ELSE 0 END)",("deposit","dépôt")),
        "withdrawals":Metric("Observed Approved Withdrawals","SUM(CASE WHEN transaction_type='Withdrawal' AND transaction_status='Approved' THEN amount ELSE 0 END)",("withdrawal","retrait")),
        "fees":Metric("Observed Processing Fees","SUM(processing_fee)",("fee","frais")),
    }, ("payment","paiement","transaction","deposit","dépôt","withdrawal","retrait")),
    "acquisition": Dataset("mart_acquisition_daily", "metric_date", {"country":"country","channel":"channel","day":"DATE(metric_date)","month":"STRFTIME('%Y-%m',metric_date)"}, {
        "registrations":Metric("Observed Registrations","SUM(registrations)",("registration","inscription")), "ftd":Metric("Observed FTD","SUM(ftd)",("ftd","first deposit","premier dépôt")),
        "conversion":Metric("Observed FTD Conversion","SUM(ftd)*1.0/NULLIF(SUM(registrations),0)",("conversion",)), "kyc":Metric("Observed KYC Verified","SUM(kyc_verified)",("kyc","verified")),
    }, ("acquisition","marketing","channel","canal","registration","ftd","conversion")),
    "players": Dataset("v_player_scores", None, {"country":"country","channel":"channel","device":"device","vip_level":"vip_level","kyc_status":"kyc_status","age_group":"age_group"}, {
        "players":Metric("Observed Players","COUNT(DISTINCT player_id)",("player","joueur","customer","client")), "lifetime_ggr":Metric("Observed Lifetime GGR","SUM(lifetime_ggr)",("lifetime ggr","value","valeur")),
        "ltv":Metric("Predicted LTV Proxy 90D","SUM(predicted_ltv_90d)",("ltv",)), "churn":Metric("Predicted Churn Risk","AVG(churn_probability)",("churn","attrition")),
        "fraud":Metric("Predicted Fraud Risk","AVG(fraud_risk)",("fraud",)), "rg":Metric("Predicted RG Risk","AVG(rg_risk)",("responsible gaming","rg risk")),
    }, ("player","joueur","customer","client","vip","ltv","churn","fraud","responsible gaming")),
}

DIMENSION_KEYWORDS = {"country":("country","countries","pays","market","marché"),"game":("game","jeu"),"provider":("provider","fournisseur"),"game_family":("family","famille","category"),"sport":("sport",),"event":("event","événement"),"channel":("channel","canal","source"),"payment_method":("payment method","méthode","method"),"transaction_type":("transaction type","type de transaction"),"status":("status","statut"),"vip_level":("vip","tier"),"device":("device","appareil"),"kyc_status":("kyc status",),"age_group":("age","âge"),"day":("daily","day","jour"),"week":("weekly","week","semaine"),"month":("monthly","month","mois")}


class SemanticQueryEngine:
    """Compiles constrained semantic plans; model text can never become SQL."""

    def __init__(self, ctx): self.ctx = ctx

    def answer(self, question: str) -> SemanticResult | None:
        candidates=[self._llm_plan(question),self._local_plan(question)]
        plans=[]
        for candidate in candidates:
            plan=self._validate(candidate) if candidate is not None else None
            if plan is not None and plan not in plans: plans.append(plan)
        if not plans: return None
        evidence=None; plan=None
        for candidate in plans:
            try:
                evidence=self.ctx.query(self._compile(candidate));plan=candidate;break
            except (SQLQueryError,DataConnectionError):
                continue
        if evidence is None or plan is None:
            raise SQLQueryError("No validated semantic plan could be executed")
        dataset = DATASETS[plan.dataset]
        labels = {name:dataset.metrics[name].label for name in plan.metrics}
        evidence = evidence.rename(columns=labels)
        metric_labels = tuple(labels[name] for name in plan.metrics)
        dimension_label = plan.dimensions[0].replace("_"," ").title() if plan.dimensions else "Scope"
        if evidence.empty:
            answer = "No governed rows match the selected period, market and requested breakdown."
        elif plan.dimensions:
            lead = evidence.iloc[0]
            answer = f"{lead.iloc[0]} is the leading {dimension_label.lower()} by {metric_labels[0]} at {self._format(lead[metric_labels[0]], metric_labels[0])}. The result contains {len(evidence):,} grouped rows for the active scope."
        else:
            answer = "For the active scope, " + ", ".join(f"{label} is {self._format(evidence.iloc[0][label],label)}" for label in metric_labels) + "."
        chart_x = dimension_label if plan.dimensions else ""
        return SemanticResult("Open data analysis",answer,evidence,(f"{dataset.table} · governed semantic query · {self.ctx.period_label}",),
                              "Read-only allow-listed aggregation. Results describe association, not causality. Distinct player counts and additive daily metrics must not be interpreted interchangeably.",
                              .90 if os.getenv("OPENAI_API_KEY") else .82,plan.chart_type,chart_x,metric_labels)

    def _local_plan(self, question: str) -> QueryPlan | None:
        q = re.sub(r"\s+"," ",question.lower())
        preferred = None
        routes = (("players",("player","players","joueur","joueurs","vip","churn","fraud","responsible gaming")),
                  ("casino",("casino","game","games","jeu","jeux","provider","rtp")),
                  ("sportsbook",("sportsbook","sport betting","pari sportif","event exposure")),
                  ("payments",("payment","paiement","transaction","deposit","dépôt","withdrawal","retrait")),
                  ("acquisition",("acquisition","marketing","registration","inscription","ftd","conversion","roas")))
        for name,words in routes:
            if any(word in q for word in words): preferred=name; break
        scored = {name:sum(bool(re.search(re.escape(word),q)) for word in ds.keywords) for name,ds in DATASETS.items()}
        dataset_name = preferred or max(scored,key=scored.get)
        if scored[dataset_name] == 0: return None
        ds = DATASETS[dataset_name]
        metrics = [name for name,m in ds.metrics.items() if any(word in q for word in m.keywords)]
        if not metrics:
            defaults={"executive":"ggr","casino":"ggr","sportsbook":"ggr","payments":"volume","acquisition":"registrations","players":"players"}
            metrics=[defaults[dataset_name]]
        dimensions=[]
        for name,words in DIMENSION_KEYWORDS.items():
            if name in ds.dimensions and any(word in q for word in words):
                dimensions.append(name)
        dimensions=dimensions[:2]
        direction="ASC" if any(word in q for word in ("worst","lowest","bottom","moins","faible")) else "DESC"
        limit_match=re.search(r"(?:top|first|premier)\s+(\d+)",q); limit=min(int(limit_match.group(1)),100) if limit_match else 25
        return QueryPlan(dataset_name,tuple(dimensions),tuple(metrics[:3]),metrics[0],direction,limit,"line" if any(x in dimensions for x in ("day","week","month")) else "bar")

    def _llm_plan(self, question: str) -> QueryPlan | None:
        key=os.getenv("OPENAI_API_KEY","").strip()
        if not key: return None
        try:
            from openai import OpenAI
            catalogue={name:{"dimensions":list(ds.dimensions),"metrics":list(ds.metrics)} for name,ds in DATASETS.items()}
            schema={"type":"object","properties":{"dataset":{"type":"string","enum":list(DATASETS)},"dimensions":{"type":"array","items":{"type":"string"},"maxItems":2},"metrics":{"type":"array","items":{"type":"string"},"minItems":1,"maxItems":3},"order_metric":{"type":"string"},"order_direction":{"type":"string","enum":["ASC","DESC"]},"limit":{"type":"integer","minimum":1,"maximum":100},"chart_type":{"type":"string","enum":["bar","line","table"]}},"required":["dataset","dimensions","metrics","order_metric","order_direction","limit","chart_type"],"additionalProperties":False}
            response=OpenAI(api_key=key,timeout=8.0,max_retries=1).responses.create(model=os.getenv("OPENAI_MODEL","gpt-5.6"),store=False,
                instructions="Translate the casino business question into one semantic query plan using only the supplied catalogue. Never invent a field. Choose the smallest useful result.",
                input=json.dumps({"question":question,"catalogue":catalogue}),text={"format":{"type":"json_schema","name":"semantic_query_plan","strict":True,"schema":schema}})
            return QueryPlan(**json.loads(response.output_text))
        except Exception: return None

    @staticmethod
    def _validate(plan: QueryPlan) -> QueryPlan | None:
        ds=DATASETS.get(plan.dataset)
        if not ds or not plan.metrics or any(x not in ds.metrics for x in plan.metrics) or any(x not in ds.dimensions for x in plan.dimensions): return None
        if plan.order_metric not in plan.metrics or plan.order_direction not in ("ASC","DESC") or plan.chart_type not in ("bar","line","table"): return None
        return QueryPlan(plan.dataset,tuple(plan.dimensions[:2]),tuple(plan.metrics[:3]),plan.order_metric,plan.order_direction,max(1,min(int(plan.limit),100)),plan.chart_type)

    def _compile(self, plan: QueryPlan) -> str:
        ds=DATASETS[plan.dataset]; dimensions=[f"{ds.dimensions[name]} AS \"{name.replace('_',' ').title()}\"" for name in plan.dimensions]
        metrics=[f"{ds.metrics[name].expression} AS \"{name}\"" for name in plan.metrics]
        clauses=[]
        if ds.date_field: clauses.append(f"{ds.date_field}>=:start AND {ds.date_field}<:end")
        if "country" in ds.dimensions: clauses.append("(:country='All markets' OR country=:country)")
        group=f" GROUP BY {','.join(str(i+1) for i in range(len(dimensions)))}" if dimensions else ""
        return f"SELECT {','.join(dimensions+metrics)} FROM {ds.table} WHERE {' AND '.join(clauses) if clauses else '1=1'}{group} ORDER BY \"{plan.order_metric}\" {plan.order_direction} LIMIT {plan.limit}"

    @staticmethod
    def _format(value, label: str) -> str:
        if value is None or pd.isna(value): return "missing data"
        number=float(value)
        if any(word in label for word in ("Rate","Risk","Margin","RTP","Hold","Conversion")): return f"{number:.1%}"
        if any(word in label for word in ("GGR","NGR","Deposits","Withdrawals","Volume","Fees","Wagers","Handle","Payout","LTV")): return f"${number:,.0f}"
        return f"{number:,.0f}"
