from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import threading
from io import BytesIO
from pathlib import Path

import pandas as pd

from auth.service import record_import
from config import DB_PATH, ROOT
from data.warehouse import build_warehouse


TENANT_ROOT = Path(os.getenv("GAMBIT_TENANT_ROOT", ROOT / "data" / "tenants"))
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_IMPORT_LOCK = threading.Lock()

TABLE_SCHEMAS = {
    "players": ["player_id", "registration_date", "country", "channel", "device", "vip_level", "kyc_status", "age_group"],
    "games": ["game_id", "game_name", "game_family", "theoretical_rtp", "provider"],
    "sessions": ["session_id", "player_id", "game_id", "session_start", "duration_minutes", "total_bet_amount", "total_payout_amount", "casino_ggr", "bet_count"],
    "transactions": ["transaction_id", "player_id", "transaction_date", "transaction_type", "amount", "transaction_status", "payment_method", "processing_fee"],
    "sports_bets": ["bet_id", "player_id", "bet_date", "sport", "is_live", "odds", "stake", "payout", "sportsbook_ggr", "event_name"],
}
REQUIRED_COLUMNS = {key: set(values) - ({"casino_ggr"} if key == "sessions" else {"sportsbook_ggr"} if key == "sports_bets" else set()) for key, values in TABLE_SCHEMAS.items()}


class ImportValidationError(ValueError):
    pass


def tenant_db_path(user_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9]", "", user_id)
    if not safe_id:
        raise ValueError("Invalid user identifier")
    return TENANT_ROOT / safe_id / "warehouse.db"


def tenant_has_data(user_id: str) -> bool:
    path = tenant_db_path(user_id)
    if not path.exists():
        return False
    try:
        with sqlite3.connect(path) as connection:
            return bool(connection.execute("SELECT COUNT(*) FROM dim_player").fetchone()[0])
    except sqlite3.Error:
        return False


def provision_demo_tenant(user_id: str) -> Path:
    target = tenant_db_path(user_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB_PATH, target)
    with sqlite3.connect(target) as connection:
        connection.execute("INSERT OR REPLACE INTO app_metadata VALUES('tenant_source','demo')")
        connection.commit()
    return target


def _table_name(file_name: str, sheet_name: str, sheet_count: int) -> str | None:
    normalize = lambda value: re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    sheet = normalize(sheet_name)
    stem = normalize(Path(file_name).stem)
    aliases = {"sportsbets": "sports_bets", "bets": "sports_bets", "player": "players", "game": "games", "session": "sessions", "transaction": "transactions"}
    for candidate in [sheet, stem if sheet_count == 1 else ""]:
        candidate = aliases.get(candidate, candidate)
        if candidate in TABLE_SCHEMAS:
            return candidate
    return None


def _normalize_frame(table: str, frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_") for column in frame.columns]
    missing = sorted(REQUIRED_COLUMNS[table] - set(frame.columns))
    if missing:
        raise ImportValidationError(f"Sheet '{table}' is missing columns: {', '.join(missing)}")
    if table == "sessions" and "casino_ggr" not in frame:
        frame["casino_ggr"] = pd.to_numeric(frame.total_bet_amount, errors="coerce") - pd.to_numeric(frame.total_payout_amount, errors="coerce")
    if table == "sports_bets" and "sportsbook_ggr" not in frame:
        frame["sportsbook_ggr"] = pd.to_numeric(frame.stake, errors="coerce") - pd.to_numeric(frame.payout, errors="coerce")
    frame = frame[TABLE_SCHEMAS[table]].dropna(how="all")
    identifier = TABLE_SCHEMAS[table][0]
    if frame[identifier].isna().any() or frame[identifier].astype(str).str.strip().eq("").any():
        raise ImportValidationError(f"Sheet '{table}' contains a blank {identifier}.")
    # Excel commonly interprets values such as "None" as empty cells. Preserve
    # the record and make optional descriptive dimensions explicit.
    descriptive = {
        "players": ["country", "channel", "device", "vip_level", "kyc_status", "age_group"],
        "games": ["game_name", "game_family", "provider"],
        "transactions": ["payment_method"],
        "sports_bets": ["sport", "event_name"],
    }.get(table, [])
    for column in descriptive:
        frame[column] = frame[column].fillna("Unknown").replace("", "Unknown")
    return frame


def parse_excel_files(files) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    collected: dict[str, list[pd.DataFrame]] = {name: [] for name in TABLE_SCHEMAS}
    for uploaded in files:
        payload = uploaded.getvalue()
        if len(payload) > MAX_UPLOAD_BYTES:
            raise ImportValidationError(f"{uploaded.name} exceeds the 25 MB per-file limit.")
        try:
            sheets = pd.read_excel(BytesIO(payload), sheet_name=None, engine="openpyxl")
        except Exception as exc:
            raise ImportValidationError(f"{uploaded.name} is not a readable Excel workbook.") from exc
        matched = 0
        for sheet_name, frame in sheets.items():
            table = _table_name(uploaded.name, sheet_name, len(sheets))
            if table:
                collected[table].append(_normalize_frame(table, frame))
                matched += 1
        if not matched:
            raise ImportValidationError(f"{uploaded.name} has no recognized sheet. Use: {', '.join(TABLE_SCHEMAS)}.")
    frames = {
        name: pd.concat(collected[name], ignore_index=True)
        if collected[name]
        else pd.DataFrame(columns=TABLE_SCHEMAS[name])
        for name in TABLE_SCHEMAS
    }
    if frames["players"].empty:
        raise ImportValidationError("A non-empty 'players' sheet is required.")
    if frames["sessions"].empty and frames["transactions"].empty and frames["sports_bets"].empty:
        raise ImportValidationError("At least one activity sheet is required: sessions, transactions or sports_bets.")
    if not frames["sessions"].empty and frames["games"].empty:
        raise ImportValidationError("The 'games' sheet is required when sessions are provided.")
    for table, frame in frames.items():
        identifier = TABLE_SCHEMAS[table][0]
        if not frame.empty and frame[identifier].astype(str).duplicated().any():
            raise ImportValidationError(f"Sheet '{table}' contains duplicate {identifier} values.")
    return frames, {table: len(frame) for table, frame in frames.items()}


def _create_fallback_models(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        players = pd.read_sql_query("SELECT player_id FROM players", connection)
        scores = players.assign(
            predicted_ltv_90d=None, churn_probability=None, fraud_risk=None, rg_risk=None,
            recommended_action="Missing data", model_confidence=None, last_session=None,
            session_count=0, lifetime_ggr=None, model_version="unavailable", scored_at=None,
        )
        scores.to_sql("model_scores", connection, if_exists="replace", index=False)
        pd.DataFrame(columns=["model_name", "metric_name", "metric_value", "model_version", "measured_at"]).to_sql("model_metrics", connection, if_exists="replace", index=False)
        pd.DataFrame(columns=["forecast_date", "predicted_revenue", "lower_bound", "upper_bound", "model_version"]).to_sql("revenue_forecast", connection, if_exists="replace", index=False)


def ingest_excel_workbooks(user_id: str, files) -> tuple[Path, dict[str, int], str]:
    if not files:
        raise ImportValidationError("Select at least one Excel workbook.")
    frames, manifest = parse_excel_files(files)
    target = tenant_db_path(user_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name("warehouse.building.db")
    if temporary.exists():
        temporary.unlink()
    filenames = ", ".join(uploaded.name for uploaded in files)
    try:
        with _IMPORT_LOCK:
            with sqlite3.connect(temporary) as connection:
                for table, frame in frames.items():
                    frame.to_sql(f"raw_{table}", connection, if_exists="replace", index=False)
            build_warehouse(temporary, include_ml=False)
            model_status = "available"
            try:
                from ml.pipeline import train_and_score
                train_and_score(temporary, target.parent / "models")
            except Exception:
                model_status = "unavailable"
                _create_fallback_models(temporary)
            build_warehouse(temporary, include_ml=True)
            with sqlite3.connect(temporary) as connection:
                connection.execute("INSERT OR REPLACE INTO app_metadata VALUES('tenant_source','excel')")
                connection.execute("INSERT OR REPLACE INTO app_metadata VALUES('model_status',?)", (model_status,))
                connection.execute("INSERT OR REPLACE INTO app_metadata VALUES('source_manifest',?)", (json.dumps(manifest, sort_keys=True),))
                connection.commit()
            os.replace(temporary, target)
        record_import(user_id, filenames, "SUCCESS", sum(manifest.values()), json.dumps(manifest))
        return target, manifest, model_status
    except Exception as exc:
        if temporary.exists():
            temporary.unlink()
        record_import(user_id, filenames, "FAILED", 0, json.dumps(manifest), str(exc)[:1000])
        if isinstance(exc, ImportValidationError):
            raise
        raise ImportValidationError(f"Import failed safely: {exc}") from exc
