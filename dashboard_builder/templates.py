from __future__ import annotations

"""Prebuilt dashboard templates. Each is a plain list of Widget kwargs so a future AI dashboard
generator (see module docstring in query_engine.py) can produce the exact same shape — a JSON
widget list — instead of needing a separate code path."""

from dashboard_builder.models import Dashboard, Widget

KPI_ROW_Y = 0
KPI_H = 3


def _kpi_row(specs: list[tuple[str, str, str]], comparison: str = "previous_period") -> list[Widget]:
    """specs: list of (title, dataset, measure)."""
    widgets = []
    for index, (title, dataset, measure) in enumerate(specs):
        widgets.append(Widget(
            type="kpi", title=title, x=(index % 4) * 3, y=KPI_ROW_Y + (index // 4) * KPI_H, w=3, h=KPI_H,
            dataset=dataset, measures=[measure], comparison=comparison,
        ))
    return widgets


def casino_executive_performance() -> list[Widget]:
    widgets = _kpi_row([
        ("GGR", "executive", "ggr"), ("Estimated NGR", "executive", "estimated_ngr"),
        ("Active Players", "player_activity", "active_players"), ("Deposits", "executive", "deposits"),
    ])
    row2_y = KPI_ROW_Y + KPI_H
    widgets += [
        Widget(type="line", title="GGR Over Time", x=0, y=row2_y, w=6, h=5, dataset="executive", dimension="day", measures=["ggr"]),
        Widget(type="bar", title="GGR by Market", x=6, y=row2_y, w=6, h=5, dataset="executive", dimension="country", measures=["ggr"]),
    ]
    row3_y = row2_y + 5
    widgets += [
        Widget(type="bar", title="Top Games by GGR", x=0, y=row3_y, w=6, h=5, dataset="casino", dimension="game", measures=["ggr"], top_n=10),
        Widget(type="bar", title="Casino RTP by Provider", x=6, y=row3_y, w=6, h=5, dataset="casino", dimension="provider", measures=["rtp"]),
    ]
    row4_y = row3_y + 5
    widgets += [
        Widget(type="line", title="Deposits vs Withdrawals", x=0, y=row4_y, w=6, h=5, dataset="executive", dimension="day", measures=["deposits", "withdrawals"]),
        Widget(type="pie", title="Active Players by VIP Level", x=6, y=row4_y, w=6, h=5, dataset="players", dimension="vip_level", measures=["players"]),
    ]
    return widgets


def executive_overview() -> list[Widget]:
    widgets = _kpi_row([
        ("GGR", "executive", "ggr"), ("Estimated NGR", "executive", "estimated_ngr"),
        ("Deposits", "executive", "deposits"), ("Withdrawals", "executive", "withdrawals"),
    ])
    row2_y = KPI_ROW_Y + KPI_H
    widgets += [
        Widget(type="line", title="GGR Over Time", x=0, y=row2_y, w=8, h=5, dataset="executive", dimension="day", measures=["ggr"]),
        Widget(type="table", title="GGR by Market", x=8, y=row2_y, w=4, h=5, dataset="executive", dimension="country", measures=["ggr", "margin"]),
    ]
    return widgets


def sportsbook_performance() -> list[Widget]:
    widgets = _kpi_row([
        ("Sportsbook GGR", "sportsbook", "ggr"), ("Handle", "sportsbook", "handle"),
        ("Payout", "sportsbook", "payout"), ("Hold", "sportsbook", "hold"),
    ], comparison="none")
    row2_y = KPI_ROW_Y + KPI_H
    widgets += [
        Widget(type="bar", title="GGR by Sport", x=0, y=row2_y, w=6, h=5, dataset="sportsbook", dimension="sport", measures=["ggr"]),
        Widget(type="bar", title="Top Events by Handle", x=6, y=row2_y, w=6, h=5, dataset="sportsbook", dimension="event", measures=["handle"], top_n=10),
    ]
    return widgets


def vip_monitoring() -> list[Widget]:
    widgets = _kpi_row([
        ("Active Players", "player_activity", "active_players"), ("Lifetime GGR", "players", "lifetime_ggr"),
        ("Predicted LTV Proxy", "players", "ltv"), ("Predicted Churn Risk", "players", "churn"),
    ], comparison="none")
    row2_y = KPI_ROW_Y + KPI_H
    widgets += [
        Widget(type="pie", title="Players by VIP Level", x=0, y=row2_y, w=6, h=5, dataset="players", dimension="vip_level", measures=["players"]),
        Widget(type="table", title="Value by VIP Level", x=6, y=row2_y, w=6, h=5, dataset="players", dimension="vip_level", measures=["lifetime_ggr", "ltv", "churn"]),
    ]
    return widgets


def acquisition_performance() -> list[Widget]:
    widgets = _kpi_row([
        ("Registrations", "acquisition", "registrations"), ("FTD", "acquisition", "ftd"),
        ("FTD Conversion", "acquisition", "conversion"), ("KYC Verified", "acquisition", "kyc"),
    ])
    row2_y = KPI_ROW_Y + KPI_H
    widgets += [
        Widget(type="line", title="Registrations Over Time", x=0, y=row2_y, w=6, h=5, dataset="acquisition", dimension="day", measures=["registrations"]),
        Widget(type="bar", title="FTD by Channel", x=6, y=row2_y, w=6, h=5, dataset="acquisition", dimension="channel", measures=["ftd"]),
    ]
    return widgets


def revenue() -> list[Widget]:
    widgets = _kpi_row([
        ("GGR", "executive", "ggr"), ("Estimated NGR", "executive", "estimated_ngr"),
        ("Deposits", "executive", "deposits"), ("Withdrawals", "executive", "withdrawals"),
    ])
    row2_y = KPI_ROW_Y + KPI_H
    widgets += [
        Widget(type="table", title="Payment Volume by Method", x=0, y=row2_y, w=6, h=5, dataset="payments", dimension="payment_method", measures=["volume", "transactions"]),
        Widget(type="bar", title="Approval Rate by Method", x=6, y=row2_y, w=6, h=5, dataset="payments", dimension="payment_method", measures=["approval_rate"]),
    ]
    return widgets


def risk_and_compliance() -> list[Widget]:
    widgets = _kpi_row([
        ("Predicted Fraud Risk", "players", "fraud"), ("Predicted RG Risk", "players", "rg"),
        ("Active Players", "player_activity", "active_players"), ("Predicted Churn Risk", "players", "churn"),
    ], comparison="none")
    row2_y = KPI_ROW_Y + KPI_H
    widgets += [
        Widget(type="table", title="Risk Scores by Market", x=0, y=row2_y, w=12, h=5, dataset="players", dimension="country", measures=["fraud", "rg", "churn"]),
    ]
    return widgets


TEMPLATES: dict[str, tuple[str, callable]] = {
    "casino_executive": ("Casino Executive Performance", casino_executive_performance),
    "executive_overview": ("Executive Overview", executive_overview),
    "sportsbook_performance": ("Sportsbook Performance", sportsbook_performance),
    "vip_monitoring": ("VIP Monitoring", vip_monitoring),
    "acquisition_performance": ("Acquisition Performance", acquisition_performance),
    "revenue": ("Revenue", revenue),
    "risk_compliance": ("Risk & Compliance", risk_and_compliance),
}


def build_from_template(template_key: str, tenant_id: str, user_id: str) -> Dashboard:
    name, builder = TEMPLATES[template_key]
    return Dashboard(tenant_id=tenant_id, user_id=user_id, name=name, widgets=builder())


def auto_generate(tenant_id: str, user_id: str) -> Dashboard:
    """"Generate Dashboard": today this deterministically assembles the highest-value governed
    metrics into the same shape a human would build (see module docstring). It is intentionally
    not a natural-language generator yet — that is the AI Dashboard Builder described in
    query_engine.py's docstring, for which this same Widget-list structure is the target output."""
    dashboard = build_from_template("casino_executive", tenant_id, user_id)
    dashboard.name = "Generated Dashboard"
    return dashboard
