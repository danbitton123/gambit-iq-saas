from __future__ import annotations

import sqlite3

import pandas as pd

from config import DB_PATH
from data.repository import SQLContext, SQLRepository
from queries.acquisition import ftd_conversion_d30
from queries.player_intelligence import retention_d30
from ui.kpi_governance import KPI_REGISTRY, kpi_help


def _context() -> SQLContext:
    return SQLContext(SQLRepository(DB_PATH), pd.Timestamp("2026-05-07"), pd.Timestamp("2026-08-04"), "All markets")


def test_observed_d30_kpis_use_mature_cohorts_and_real_activity():
    ctx = _context()
    ftd = ftd_conversion_d30.run(ctx)
    retention = retention_d30.run(ctx)

    assert ftd.eligible_registrations > 0
    assert 0 <= ftd.converted_d30 <= ftd.eligible_registrations
    assert ftd.ftd_conversion_d30 == ftd.converted_d30 / ftd.eligible_registrations
    assert retention.eligible_players > 0
    assert 0 <= retention.retained_players <= retention.eligible_players
    assert retention.retention_d30 == retention.retained_players / retention.eligible_players


def test_rtp_variance_sign_is_actual_minus_theoretical():
    with sqlite3.connect(DB_PATH) as connection:
        raw_value = connection.execute("""
            SELECT SUM(total_payout_amount)/SUM(total_bet_amount)
                   - SUM(total_bet_amount*theoretical_rtp)/SUM(total_bet_amount)
            FROM v_sessions_enriched
        """).fetchone()[0]
        mart_value = connection.execute("""
            SELECT SUM(payouts)/SUM(bets)
                   - SUM(bets*theoretical_rtp)/SUM(bets)
            FROM mart_game_performance_daily
        """).fetchone()[0]

    assert isinstance(raw_value, float)
    assert abs(raw_value - mart_value) < 1e-12


def test_every_registered_kpi_exposes_complete_contextual_help():
    required = ["Definition:", "Formula:", "Source:", "Period:", "Status:", "Last updated:"]
    assert KPI_REGISTRY
    for label in KPI_REGISTRY:
        help_text = kpi_help(label, "01 Jan 2026 – 31 Jan 2026 · Canada", "31 Jan 2026, 23:59 UTC")
        assert all(field in help_text for field in required)
