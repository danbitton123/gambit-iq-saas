from __future__ import annotations

"""Shared "active in the filtered period" predicate reused by every CRM Automation query."""

ACTIVE_CONDITION = """(:country='All markets' OR v.country=:country) AND EXISTS (SELECT 1 FROM v_sessions_enriched s WHERE s.player_id=v.player_id AND s.session_start>=:start AND s.session_start<:end)"""
