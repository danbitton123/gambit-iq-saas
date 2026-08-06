from __future__ import annotations

"""Selected market's share of the last 29 observed days of total GGR — scales the all-market forecast
down to the selected country. Returns 1.0 (no scaling) when the scope is "All markets"."""

TOTAL_RECENT_SQL = "SELECT SUM(total_ggr) FROM mart_executive_daily WHERE metric_date>=(SELECT DATE(MAX(metric_date),'-29 days') FROM mart_executive_daily)"
MARKET_RECENT_SQL = "SELECT SUM(total_ggr) FROM mart_executive_daily WHERE country=:country AND metric_date>=(SELECT DATE(MAX(metric_date),'-29 days') FROM mart_executive_daily)"


def run(ctx) -> float:
    if ctx.country == "All markets":
        return 1.0
    total_recent = ctx.repo.scalar(TOTAL_RECENT_SQL) or 0
    market_recent = ctx.repo.scalar(MARKET_RECENT_SQL, {"country": ctx.country}) or 0
    return max(float(market_recent) / float(total_recent), 0) if total_recent else 0
