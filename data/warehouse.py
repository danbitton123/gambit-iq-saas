from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "4.0-temporal-ml"
SQL_ROOT = Path(__file__).resolve().parents[1] / "sql" / "warehouse"
BASE_SCRIPTS = ["10_staging.sql", "20_dimensions.sql", "30_facts.sql", "40_intermediate.sql", "50_marts.sql"]


class WarehouseQualityError(RuntimeError):
    pass


def _drop_relation(conn: sqlite3.Connection, name: str) -> None:
    row = conn.execute("SELECT type FROM sqlite_master WHERE name=?", (name,)).fetchone()
    if row:
        conn.execute(f"DROP {row[0].upper()} IF EXISTS {name}")


def _reset_curated_layer(conn: sqlite3.Connection) -> None:
    # Dependency order matters when foreign keys are enabled.
    for name in [
        "v_player_scores", "mart_player_360", "v_sessions_enriched", "v_transactions_enriched",
        "v_sports_bets_enriched", "players", "games", "sessions", "transactions", "sports_bets",
        "int_player_first_deposit", "int_player_first_activity", "int_player_activity_daily",
        "int_daily_gaming_revenue", "stg_players", "stg_games", "stg_sessions",
        "stg_transactions", "stg_sports_bets",
    ]:
        _drop_relation(conn, name)
    for name in ["mart_executive_daily", "mart_game_performance_daily", "mart_acquisition_daily", "mart_payments_daily",
                 "fact_casino_session", "fact_transaction", "fact_sports_bet", "dim_date", "dim_player", "dim_game"]:
        _drop_relation(conn, name)


def _run_script(conn: sqlite3.Connection, filename: str) -> None:
    conn.executescript((SQL_ROOT / filename).read_text(encoding="utf-8"))


def quality_checks(conn: sqlite3.Connection, include_ml: bool = False) -> dict[str, int]:
    checks = {
        "duplicate_players": "SELECT COUNT(*)-COUNT(DISTINCT player_id) FROM dim_player",
        "duplicate_sessions": "SELECT COUNT(*)-COUNT(DISTINCT session_id) FROM fact_casino_session",
        "duplicate_transactions": "SELECT COUNT(*)-COUNT(DISTINCT transaction_id) FROM fact_transaction",
        "duplicate_sports_bets": "SELECT COUNT(*)-COUNT(DISTINCT bet_id) FROM fact_sports_bet",
        "orphan_session_players": "SELECT COUNT(*) FROM fact_casino_session f LEFT JOIN dim_player p USING(player_id) WHERE p.player_id IS NULL",
        "orphan_session_games": "SELECT COUNT(*) FROM fact_casino_session f LEFT JOIN dim_game g USING(game_id) WHERE g.game_id IS NULL",
        "orphan_transaction_players": "SELECT COUNT(*) FROM fact_transaction f LEFT JOIN dim_player p USING(player_id) WHERE p.player_id IS NULL",
        "orphan_sports_players": "SELECT COUNT(*) FROM fact_sports_bet f LEFT JOIN dim_player p USING(player_id) WHERE p.player_id IS NULL",
        "casino_ggr_mismatch": "SELECT COUNT(*) FROM fact_casino_session WHERE ABS(casino_ggr-(total_bet_amount-total_payout_amount))>.01",
        "sports_ggr_mismatch": "SELECT COUNT(*) FROM fact_sports_bet WHERE ABS(sportsbook_ggr-(stake-payout))>.01",
        "invalid_rtp": "SELECT COUNT(*) FROM dim_game WHERE theoretical_rtp NOT BETWEEN 0 AND 1",
        "raw_fact_session_delta": "SELECT ABS((SELECT COUNT(*) FROM raw_sessions)-(SELECT COUNT(*) FROM fact_casino_session))",
        "raw_fact_transaction_delta": "SELECT ABS((SELECT COUNT(*) FROM raw_transactions)-(SELECT COUNT(*) FROM fact_transaction))",
        "raw_fact_sports_delta": "SELECT ABS((SELECT COUNT(*) FROM raw_sports_bets)-(SELECT COUNT(*) FROM fact_sports_bet))",
    }
    if include_ml:
        checks |= {
            "invalid_ml_probability": "SELECT COUNT(*) FROM model_scores WHERE churn_probability NOT BETWEEN 0 AND 1 OR fraud_risk NOT BETWEEN 0 AND 1 OR rg_risk NOT BETWEEN 0 AND 1",
            "duplicate_ml_players": "SELECT COUNT(*)-COUNT(DISTINCT player_id) FROM model_scores",
            "orphan_ml_players": "SELECT COUNT(*) FROM model_scores m LEFT JOIN dim_player p USING(player_id) WHERE p.player_id IS NULL",
        }
    results = {name: int(conn.execute(sql).fetchone()[0] or 0) for name, sql in checks.items()}
    failed = {name: value for name, value in results.items() if value != 0}
    if failed:
        raise WarehouseQualityError(f"Warehouse quality checks failed: {failed}")
    return results


def build_warehouse(db_path: Path, include_ml: bool = False) -> dict[str, int]:
    started_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        # DELETE mode is the safest zero-configuration choice for a local file
        # that may be regenerated before Streamlit opens read connections.
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("""CREATE TABLE IF NOT EXISTS pipeline_runs(
            run_id INTEGER PRIMARY KEY AUTOINCREMENT, pipeline_name TEXT NOT NULL,
            started_at TEXT NOT NULL, completed_at TEXT, status TEXT NOT NULL,
            rows_loaded INTEGER DEFAULT 0, error_message TEXT)""")
        run_id = conn.execute("INSERT INTO pipeline_runs(pipeline_name,started_at,status) VALUES(?,?,?)",
                              ("warehouse_post_ml" if include_ml else "warehouse_base", started_at, "RUNNING")).lastrowid
        try:
            if include_ml:
                if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='model_scores'").fetchone():
                    raise WarehouseQualityError("model_scores is required before the post-ML mart build")
                _run_script(conn, "60_ml_marts.sql")
            else:
                _reset_curated_layer(conn)
                for script in BASE_SCRIPTS:
                    _run_script(conn, script)
            results = quality_checks(conn, include_ml=include_ml)
            conn.execute("CREATE TABLE IF NOT EXISTS app_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            conn.execute("INSERT OR REPLACE INTO app_metadata VALUES('schema_version',?)", (SCHEMA_VERSION,))
            conn.execute("INSERT OR REPLACE INTO app_metadata VALUES('warehouse_refreshed_at',?)", (datetime.now(timezone.utc).isoformat(),))
            rows_loaded = sum(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ["fact_casino_session", "fact_transaction", "fact_sports_bet"])
            conn.execute("UPDATE pipeline_runs SET completed_at=?,status='SUCCESS',rows_loaded=? WHERE run_id=?",
                         (datetime.now(timezone.utc).isoformat(), rows_loaded, run_id))
            conn.commit()
            return results
        except Exception as exc:
            conn.execute("UPDATE pipeline_runs SET completed_at=?,status='FAILED',error_message=? WHERE run_id=?",
                         (datetime.now(timezone.utc).isoformat(), str(exc)[:1000], run_id))
            conn.commit()
            raise
