from __future__ import annotations

"""Shared "active in the filtered period" predicate reused by Command Center's risk queries."""

ACTIVE_CONDITION = """(:country='All markets' OR v.country=:country) AND EXISTS (
  SELECT 1 FROM int_player_activity_daily a WHERE a.player_id=v.player_id
  AND a.activity_date>=DATE(:start) AND a.activity_date<DATE(:end))"""
