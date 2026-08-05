from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from config import DB_PATH
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
            return version is None or version[0] != SCHEMA_VERSION or not _table_exists(conn, "model_scores") or not _table_exists(conn, "mart_executive_daily")
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
        generate_database(DB_PATH)
        from ml.pipeline import train_and_score
        train_and_score(DB_PATH)
        build_warehouse(DB_PATH, include_ml=True)


@st.cache_data(show_spinner=False, ttl=300)
def _query_cached(sql: str, params_json: str, db_mtime: float) -> pd.DataFrame:
    del db_mtime
    params = json.loads(params_json)
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)


class SQLRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        ensure_database()

    def query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        serialized = json.dumps(params or {}, sort_keys=True, default=str)
        return _query_cached(sql, serialized, self.db_path.stat().st_mtime)

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
            "end": (self.end + pd.Timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "country": self.country,
        }

    def query(self, sql: str, extra: dict | None = None) -> pd.DataFrame:
        params = self.params | (extra or {})
        return self.repo.query(sql, params)

    def scalar(self, sql: str, extra: dict | None = None, default=0):
        params = self.params | (extra or {})
        return self.repo.scalar(sql, params, default)


@st.cache_resource(show_spinner="Preparing SQL warehouse and ML predictions…")
def get_repository() -> SQLRepository:
    return SQLRepository()
