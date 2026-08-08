from __future__ import annotations

"""Shared "active in the filtered period" predicate reused by every Risk & Compliance query.

Casino AND sportsbook activity — matches DecisionEngine._player_risk()'s population (the FRAUD_SIGNAL
/ RG_SIGNAL rules driving the same alerts on Command Center and AI Copilot) and Command Center's own
"Observed Active Players" KPI, which is also casino-and-sportsbook. A casino-sessions-only predicate
here previously undercounted active accounts and fraud/RG cases by excluding sportsbook-only players,
silently diverging from every other page's definition of "active"."""

ACTIVE_CONDITION = """(:country='All markets' OR v.country=:country) AND EXISTS (
  SELECT 1 FROM int_player_activity_daily a WHERE a.player_id=v.player_id
  AND a.activity_date>=DATE(:start) AND a.activity_date<DATE(:end))"""
