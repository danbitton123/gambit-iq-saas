from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.generator import generate_database
from data.warehouse import SCHEMA_VERSION, build_warehouse, quality_checks


def test_layered_warehouse_integrity(tmp_path):
    db = tmp_path / "warehouse.db"
    generate_database(db)
    with sqlite3.connect(db) as conn:
        assert quality_checks(conn) and not conn.execute("PRAGMA foreign_key_check").fetchall()
        objects = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        required = {
            "raw_players", "stg_players", "dim_player", "dim_game", "dim_date",
            "fact_casino_session", "fact_transaction", "fact_sports_bet",
            "int_player_first_deposit", "mart_executive_daily",
            "mart_game_performance_daily", "mart_acquisition_daily", "mart_payments_daily",
        }
        assert required <= objects
        raw_counts = conn.execute("SELECT (SELECT COUNT(*) FROM raw_sessions),(SELECT COUNT(*) FROM raw_transactions),(SELECT COUNT(*) FROM raw_sports_bets)").fetchone()
        fact_counts = conn.execute("SELECT (SELECT COUNT(*) FROM fact_casino_session),(SELECT COUNT(*) FROM fact_transaction),(SELECT COUNT(*) FROM fact_sports_bet)").fetchone()
        assert raw_counts == fact_counts == (72_000, 31_000, 48_000)
        raw_ggr = conn.execute("SELECT ROUND(SUM(total_bet_amount-total_payout_amount),2) FROM raw_sessions").fetchone()[0]
        fact_ggr = conn.execute("SELECT ROUND(SUM(casino_ggr),2) FROM fact_casino_session").fetchone()[0]
        mart_ggr = conn.execute("SELECT ROUND(SUM(casino_ggr),2) FROM mart_executive_daily").fetchone()[0]
        assert raw_ggr == fact_ggr == mart_ggr
        assert conn.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("SELECT COUNT(*) FROM pipeline_runs WHERE status='SUCCESS'").fetchone()[0] >= 1


def test_warehouse_rebuild_is_idempotent(tmp_path):
    db = tmp_path / "warehouse.db"
    generate_database(db)
    first = build_warehouse(db)
    second = build_warehouse(db)
    assert first == second
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM fact_casino_session").fetchone()[0] == 72_000
        assert conn.execute("SELECT COUNT(*) FROM mart_game_performance_daily").fetchone()[0] > 0
