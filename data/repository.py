from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

from config import DB_PATH
from data.errors import DataConnectionError, SQLQueryError
from data.generator import generate_database
from data.warehouse import SCHEMA_VERSION, build_warehouse


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (table,)
    ).fetchone() is not None


_BUILD_LOCK = threading.Lock()


def _needs_rebuild() -> bool:
    if not DB_PATH.exists():
        return True
    try:
        with sqlite3.connect(DB_PATH) as conn:
            version = conn.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()
            return (
                version is None or version[0] != SCHEMA_VERSION
                or not _table_exists(conn, "model_scores")
                or not _table_exists(conn, "model_metrics_v2")
                or not _table_exists(conn, "forecast_backtest")
                or not _table_exists(conn, "next_best_actions")
                or not _table_exists(conn, "mart_executive_daily")
            )
    except sqlite3.Error:
        return True


def ensure_database() -> None:
    if not _needs_rebuild():
        return
    # Streamlit can execute the script more than once during startup. The second
    # check prevents two threads from rebuilding the same free local database.
    with _BUILD_LOCK:
        if not _needs_rebuild():
            return
        # Build into a uniquely-named candidate file and swap it in atomically (same pattern
        # as the CSV importer's activation) instead of regenerating DB_PATH in place: another
        # session querying the live file mid-rebuild would otherwise hit "no such table"
        # between a DROP and its CREATE. The unique name also means two processes racing to
        # rebuild (e.g. two replicas sharing a volume) never step on each other's candidate.
        candidate = DB_PATH.with_name(f"{DB_PATH.stem}.rebuild.{uuid4().hex[:8]}{DB_PATH.suffix}")
        try:
            generate_database(candidate)
            from ml.pipeline import train_and_score
            train_and_score(candidate)
            build_warehouse(candidate, include_ml=True)
            os.replace(candidate, DB_PATH)
        finally:
            if candidate.exists():
                candidate.unlink()


_TRANSIENT_SCHEMA_ERRORS = ("no such table", "no such column", "unable to open", "locked")


@st.cache_data(show_spinner=False, ttl=300)
def _query_cached(sql: str, params_json: str, db_path: str, db_mtime: float) -> pd.DataFrame:
    del db_mtime
    params = json.loads(params_json)
    last_exc: Exception | None = None
    # "no such table"/"no such column" can appear as a brief, transient read against a
    # warehouse another process is mid-rebuilding (a swap lands between this retry loop's
    # attempts) even though the rebuild itself now swaps in atomically; a couple of short
    # retries turn that into an invisible delay instead of a hard error surfaced to the user.
    for attempt in range(3):
        try:
            with sqlite3.connect(db_path) as conn:
                return pd.read_sql_query(sql, conn, params=params)
        except sqlite3.OperationalError as exc:
            last_exc = exc
            message = str(exc).lower()
            if any(pattern in message for pattern in _TRANSIENT_SCHEMA_ERRORS) and attempt < 2:
                time.sleep(0.4 * (attempt + 1))
                continue
            if "unable to open" in message or "locked" in message:
                raise DataConnectionError("Warehouse connection failed") from exc
            raise SQLQueryError("SQL operation failed") from exc
        except (sqlite3.Error, pd.errors.DatabaseError) as exc:
            raise SQLQueryError("SQL query failed") from exc
    raise SQLQueryError("SQL operation failed") from last_exc


class SQLRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        if self.db_path == DB_PATH:
            ensure_database()
        elif not self.db_path.exists():
            raise DataConnectionError("Tenant warehouse is unavailable")

    def query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        serialized = json.dumps(params or {}, sort_keys=True, default=str)
        try:
            mtime = self.db_path.stat().st_mtime
        except OSError as exc:
            raise DataConnectionError("Warehouse file is unavailable") from exc
        return _query_cached(sql, serialized, str(self.db_path), mtime)

    def scalar(self, sql: str, params: dict | None = None, default=0):
        df = self.query(sql, params)
        return default if df.empty else df.iat[0, 0]

    def date_bounds(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        row = self.query(
            """
            SELECT MIN(event_date) AS min_date, MAX(event_date) AS max_date
            FROM (
                SELECT DATE(session_start) AS event_date FROM sessions
                UNION ALL SELECT DATE(transaction_date) FROM transactions
                UNION ALL SELECT DATE(bet_date) FROM sports_bets
            )
            """
        ).iloc[0]
        return pd.Timestamp(row.min_date), pd.Timestamp(row.max_date)

    def countries(self) -> list[str]:
        return self.query("SELECT DISTINCT country FROM players ORDER BY country")["country"].tolist()

    def latest_event(self) -> pd.Timestamp | None:
        value = self.scalar("""
            SELECT MAX(event_timestamp) FROM (
              SELECT session_start AS event_timestamp FROM sessions
              UNION ALL SELECT transaction_date FROM transactions
              UNION ALL SELECT bet_date FROM sports_bets
            )
        """, default=None)
        return pd.Timestamp(value) if value else None

    def model_available(self) -> bool:
        status = self.scalar("SELECT value FROM app_metadata WHERE key='model_status'", default=None)
        if status == "unavailable":
            return False
        count = self.scalar("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type IN ('table','view') AND name IN ('model_scores','model_metrics')
        """, default=0)
        return int(count or 0) == 2


@dataclass(frozen=True)
class SQLContext:
    repo: SQLRepository
    start: pd.Timestamp
    end: pd.Timestamp
    country: str

    @property
    def params(self) -> dict:
        return {
            "start": self.start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": (self.end + pd.Timedelta(1, unit="D")).strftime("%Y-%m-%d %H:%M:%S"),
            "country": self.country,
        }

    @property
    def previous_params(self) -> dict:
        """Parameters for the immediately preceding, equally sized period."""
        days = (self.end.normalize() - self.start.normalize()).days + 1
        previous_end = self.start.normalize()
        previous_start = previous_end - pd.Timedelta(days, unit="D")
        return {
            "start": previous_start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": previous_end.strftime("%Y-%m-%d %H:%M:%S"),
            "country": self.country,
        }

    def query(self, sql: str, extra: dict | None = None) -> pd.DataFrame:
        params = self.params | (extra or {})
        return self.repo.query(sql, params)

    def scalar(self, sql: str, extra: dict | None = None, default=0):
        params = self.params | (extra or {})
        return self.repo.scalar(sql, params, default)

    def previous_query(self, sql: str, extra: dict | None = None) -> pd.DataFrame:
        params = self.previous_params | (extra or {})
        return self.repo.query(sql, params)

    def previous_scalar(self, sql: str, extra: dict | None = None, default=0):
        params = self.previous_params | (extra or {})
        return self.repo.scalar(sql, params, default)

    def event_count(self) -> int:
        """Count activity represented by the global date and market filters."""
        return int(self.scalar("""
            SELECT COUNT(*) FROM (
              SELECT s.player_id FROM v_sessions_enriched s
              WHERE s.session_start>=:start AND s.session_start<:end
                AND (:country='All markets' OR s.country=:country)
              UNION ALL
              SELECT t.player_id FROM v_transactions_enriched t
              WHERE t.transaction_date>=:start AND t.transaction_date<:end
                AND (:country='All markets' OR t.country=:country)
              UNION ALL
              SELECT b.player_id FROM v_sports_bets_enriched b
              WHERE b.bet_date>=:start AND b.bet_date<:end
                AND (:country='All markets' OR b.country=:country)
            )
        """, default=0) or 0)

    @property
    def period_label(self) -> str:
        return f"{self.start:%d %b %Y} – {self.end:%d %b %Y} · {self.country}"

    def last_updated_label(self) -> str:
        value = self.scalar("""
            SELECT MAX(event_timestamp) FROM (
              SELECT s.session_start event_timestamp FROM v_sessions_enriched s
              WHERE s.session_start>=:start AND s.session_start<:end
                AND (:country='All markets' OR s.country=:country)
              UNION ALL
              SELECT t.transaction_date FROM v_transactions_enriched t
              WHERE t.transaction_date>=:start AND t.transaction_date<:end
                AND (:country='All markets' OR t.country=:country)
              UNION ALL
              SELECT b.bet_date FROM v_sports_bets_enriched b
              WHERE b.bet_date>=:start AND b.bet_date<:end
                AND (:country='All markets' OR b.country=:country)
            )
        """, default=None)
        if not value:
            return "No matching refresh"
        return f"{pd.Timestamp(value):%d %b %Y, %H:%M} UTC"


@st.cache_resource(show_spinner="Preparing SQL warehouse and ML predictions…")
def get_repository(db_path: str | None = None) -> SQLRepository:
    if db_path:
        return SQLRepository(Path(db_path))
    from data.importer import active_database
    return SQLRepository(active_database() or DB_PATH)
