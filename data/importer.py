from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4

import pandas as pd

from config import ROOT
from data.warehouse import build_warehouse


IMPORT_ROOT = ROOT / "data" / "imports"
ACTIVE_DB = IMPORT_ROOT / "active_warehouse.db"
REGISTRY_DB = IMPORT_ROOT / "import_registry.db"
MAX_FILE_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class FieldSpec:
    kind: str
    required: bool = True
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class DataContract:
    label: str
    primary_key: str
    fields: dict[str, FieldSpec]


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    dataset: str
    column: str
    row: int | None
    code: str
    message: str


def F(kind: str, required: bool = True, *aliases: str) -> FieldSpec:
    return FieldSpec(kind, required, aliases)


CONTRACTS: dict[str, DataContract] = {
    "games": DataContract("Games", "game_id", {
        "game_id": F("text", True, "gameid"), "game_name": F("text", True, "name", "title"),
        "game_family": F("text", False, "category", "game_type"),
        "theoretical_rtp": F("number", False, "rtp", "expected_rtp"), "provider": F("text", False, "supplier", "vendor"),
    }),
    "players": DataContract("Players", "player_id", {
        "player_id": F("text", True, "playerid", "customer_id", "user_id"),
        "registration_date": F("datetime", True, "registered_at", "signup_date", "created_at"),
        "country": F("text", True, "market", "jurisdiction"), "channel": F("text", False, "acquisition_channel", "source"),
        "device": F("text", False, "device_type"), "vip_level": F("text", False, "vip", "tier"),
        "kyc_status": F("text", False, "kyc", "verification_status"), "age_group": F("text", False, "age_band"),
    }),
    "casino_sessions": DataContract("Casino sessions", "session_id", {
        "session_id": F("text", True, "sessionid"), "player_id": F("text", True, "playerid", "customer_id"),
        "game_id": F("text", True, "gameid"), "session_start": F("datetime", True, "started_at", "session_date"),
        "duration_minutes": F("number", False, "duration", "minutes"), "total_bet_amount": F("number", True, "bets", "wager_amount"),
        "total_payout_amount": F("number", True, "payouts", "win_amount"), "casino_ggr": F("number", False, "ggr"),
        "bet_count": F("integer", False, "bets_count", "number_of_bets"), "game_name": F("text", False, "game"),
        "game_family": F("text", False, "category"), "theoretical_rtp": F("number", False, "rtp", "expected_rtp"),
        "provider": F("text", False, "supplier", "vendor"),
    }),
    "sportsbook_bets": DataContract("Sportsbook bets", "bet_id", {
        "bet_id": F("text", True, "betid"), "player_id": F("text", True, "playerid", "customer_id"),
        "bet_date": F("datetime", True, "placed_at", "created_at"), "sport": F("text", True, "sport_name"),
        "is_live": F("boolean", False, "live", "in_play"), "odds": F("number", True, "price"),
        "stake": F("number", True, "bet_amount"), "payout": F("number", True, "win_amount"),
        "sportsbook_ggr": F("number", False, "ggr"), "event_name": F("text", False, "event", "fixture"),
    }),
    "transactions": DataContract("Transactions", "transaction_id", {
        "transaction_id": F("text", True, "transactionid", "payment_id"), "player_id": F("text", True, "playerid", "customer_id"),
        "transaction_date": F("datetime", True, "created_at", "payment_date"), "transaction_type": F("text", True, "type"),
        "amount": F("number", True, "value"), "transaction_status": F("text", True, "status"),
        "payment_method": F("text", False, "method", "provider"), "processing_fee": F("number", False, "fee"),
    }),
    "bonuses": DataContract("Bonuses", "bonus_id", {
        "bonus_id": F("text", True, "bonusid"), "player_id": F("text", True, "playerid", "customer_id"),
        "bonus_date": F("datetime", True, "granted_at", "created_at"), "bonus_type": F("text", True, "type"),
        "bonus_amount": F("number", True, "amount", "cost"), "bonus_status": F("text", False, "status"),
        "campaign_id": F("text", False, "campaignid"),
    }),
    "campaigns": DataContract("Campaigns", "campaign_id", {
        "campaign_id": F("text", True, "campaignid"), "campaign_name": F("text", True, "name"),
        "channel": F("text", True, "marketing_channel"), "start_date": F("datetime", True, "started_at"),
        "end_date": F("datetime", False, "ended_at"), "spend": F("number", False, "cost", "budget"),
        "impressions": F("integer", False), "clicks": F("integer", False), "conversions": F("integer", False),
    }),
    "kyc_risk_events": DataContract("KYC / risk events", "event_id", {
        "event_id": F("text", True, "risk_event_id", "case_id"), "player_id": F("text", True, "playerid", "customer_id"),
        "event_date": F("datetime", True, "created_at", "detected_at"), "event_type": F("text", True, "type", "risk_type"),
        "severity": F("text", True, "risk_level"), "status": F("text", False, "case_status"),
        "risk_score": F("number", False, "score"), "source": F("text", False, "system"),
    }),
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def read_csv_payload(name: str, payload: bytes) -> pd.DataFrame:
    if not payload or len(payload) > MAX_FILE_BYTES:
        raise ValueError(f"{name}: file must be non-empty and no larger than 50 MB.")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{name}: use UTF-8 encoding.") from exc
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        frame = pd.read_csv(StringIO(text), sep=dialect.delimiter, dtype=object)
    except Exception as exc:
        raise ValueError(f"{name}: unreadable CSV structure.") from exc
    frame.columns = [str(column).strip() for column in frame.columns]
    if frame.empty or not len(frame.columns):
        raise ValueError(f"{name}: CSV contains no data rows.")
    return frame


def infer_dataset(filename: str, columns) -> str:
    stem = _norm(Path(filename).stem)
    aliases = {"sessions":"casino_sessions", "casino":"casino_sessions", "bets":"sportsbook_bets", "sports_bets":"sportsbook_bets", "risk_events":"kyc_risk_events", "kyc":"kyc_risk_events"}
    for name in CONTRACTS:
        if name in stem or aliases.get(stem) == name:
            return name
    normalized = {_norm(column) for column in columns}
    scores = {}
    for name, contract in CONTRACTS.items():
        candidates = {field for field in contract.fields}
        candidates |= {_norm(alias) for spec in contract.fields.values() for alias in spec.aliases}
        scores[name] = len(normalized & candidates)
    return max(scores, key=scores.get)


def suggest_mapping(dataset: str, columns) -> dict[str, str | None]:
    normalized = {_norm(column): column for column in columns}
    result = {}
    for field, spec in CONTRACTS[dataset].fields.items():
        options = [_norm(field), *(_norm(alias) for alias in spec.aliases)]
        result[field] = next((normalized[item] for item in options if item in normalized), None)
    return result


def _coerce(series: pd.Series, kind: str) -> tuple[pd.Series, pd.Series]:
    original_present = series.notna() & series.astype(str).str.strip().ne("")
    if kind in {"number", "integer"}:
        converted = pd.to_numeric(series, errors="coerce")
        if kind == "integer": converted = converted.round().astype("Int64")
    elif kind == "datetime":
        converted = pd.to_datetime(series, errors="coerce", utc=True).dt.tz_localize(None)
    elif kind == "boolean":
        lookup = {"1":1,"true":1,"yes":1,"y":1,"live":1,"0":0,"false":0,"no":0,"n":0,"prematch":0,"pre_match":0}
        converted = series.astype(str).str.strip().str.lower().map(lookup).astype("Int64")
    else:
        converted = series.astype("string").str.strip().replace({"":pd.NA,"nan":pd.NA,"none":pd.NA})
    return converted, original_present & converted.isna()


def validate_frame(dataset: str, source: pd.DataFrame, mapping: dict[str, str | None]) -> tuple[pd.DataFrame, list[QualityIssue]]:
    contract = CONTRACTS[dataset]; issues: list[QualityIssue] = []; mapped = pd.DataFrame(index=source.index)
    used = [column for column in mapping.values() if column]
    duplicates = sorted({column for column in used if used.count(column)>1})
    for column in duplicates:
        issues.append(QualityIssue("ERROR",dataset,column,None,"DUPLICATE_MAPPING",f"Source column '{column}' is mapped more than once."))
    for field, spec in contract.fields.items():
        source_column = mapping.get(field)
        if not source_column or source_column not in source.columns:
            mapped[field] = pd.NA
            if spec.required:
                issues.append(QualityIssue("ERROR",dataset,field,None,"MISSING_COLUMN",f"Required field '{field}' is not mapped."))
            continue
        converted, invalid = _coerce(source[source_column], spec.kind)
        mapped[field] = converted
        for row in source.index[invalid][:25]:
            issues.append(QualityIssue("ERROR",dataset,field,int(row)+2,"INVALID_TYPE",f"Value cannot be parsed as {spec.kind}."))
        missing_count = int(converted.isna().sum())
        if spec.required and missing_count:
            issues.append(QualityIssue("ERROR",dataset,field,None,"MISSING_VALUE",f"{missing_count:,} required values are missing."))
        elif missing_count:
            issues.append(QualityIssue("WARNING",dataset,field,None,"OPTIONAL_MISSING",f"{missing_count:,} optional values are missing."))
    key = contract.primary_key
    if key in mapped:
        duplicate_count = int(mapped[key].dropna().duplicated().sum())
        if duplicate_count:
            issues.append(QualityIssue("ERROR",dataset,key,None,"DUPLICATE_KEY",f"{duplicate_count:,} duplicate primary keys detected."))
    numeric_nonnegative = {
        "casino_sessions":["duration_minutes","total_bet_amount","total_payout_amount","bet_count"],
        "sportsbook_bets":["odds","stake","payout"], "transactions":["amount","processing_fee"],
        "bonuses":["bonus_amount"], "campaigns":["spend","impressions","clicks","conversions"],
    }.get(dataset, [])
    for field in numeric_nonnegative:
        if field in mapped and (pd.to_numeric(mapped[field],errors="coerce")<0).any():
            issues.append(QualityIssue("ERROR",dataset,field,None,"INVALID_RANGE",f"'{field}' cannot be negative."))
    if dataset == "games":
        if mapped.theoretical_rtp.notna().any() and (~mapped.theoretical_rtp.between(0,1)).any(): issues.append(QualityIssue("ERROR",dataset,"theoretical_rtp",None,"INVALID_RANGE","RTP must be between 0 and 1."))
        mapped["theoretical_rtp"] = mapped.theoretical_rtp.fillna(.96)
    if dataset == "casino_sessions":
        mapped["casino_ggr"] = mapped.casino_ggr.fillna(mapped.total_bet_amount-mapped.total_payout_amount)
        mapped["duration_minutes"] = mapped.duration_minutes.fillna(0); mapped["bet_count"] = mapped.bet_count.fillna(0)
        if mapped.theoretical_rtp.notna().any() and (~mapped.theoretical_rtp.between(0,1)).any(): issues.append(QualityIssue("ERROR",dataset,"theoretical_rtp",None,"INVALID_RANGE","RTP must be between 0 and 1."))
    if dataset == "sportsbook_bets":
        mapped["sportsbook_ggr"] = mapped.sportsbook_ggr.fillna(mapped.stake-mapped.payout); mapped["is_live"] = mapped.is_live.fillna(0)
        if (mapped.odds.dropna()<1).any(): issues.append(QualityIssue("ERROR",dataset,"odds",None,"INVALID_RANGE","Decimal odds must be at least 1."))
    if dataset == "transactions":
        domains = {"transaction_type":{"deposit","withdrawal"}, "transaction_status":{"approved","declined","pending"}}
        for field, allowed in domains.items():
            invalid = mapped[field].dropna().astype(str).str.lower().map(lambda value: value not in allowed)
            if invalid.any():
                issues.append(QualityIssue("ERROR",dataset,field,None,"INVALID_DOMAIN",f"'{field}' contains values outside: {', '.join(sorted(allowed))}."))
    if dataset == "campaigns":
        if mapped.end_date.notna().any() and (mapped.end_date < mapped.start_date).fillna(False).any():
            issues.append(QualityIssue("ERROR",dataset,"end_date",None,"INVALID_DATE_ORDER","Campaign end date cannot precede its start date."))
        if (mapped.clicks > mapped.impressions).fillna(False).any() or (mapped.conversions > mapped.clicks).fillna(False).any():
            issues.append(QualityIssue("ERROR",dataset,"funnel",None,"INVALID_FUNNEL","Campaign funnel counts must satisfy conversions <= clicks <= impressions."))
    if dataset == "kyc_risk_events" and mapped.risk_score.notna().any() and (~mapped.risk_score.between(0,1)).any():
        issues.append(QualityIssue("ERROR",dataset,"risk_score",None,"INVALID_RANGE","Risk score must be between 0 and 1."))
    defaults = {"channel":"Unknown","device":"Unknown","vip_level":"Standard","kyc_status":"Unknown","age_group":"Unknown","payment_method":"Unknown","event_name":"Unknown","provider":"Unknown","game_name":"Unknown","game_family":"Unknown","transaction_status":"Pending","bonus_status":"Unknown","status":"Open","source":"Unknown"}
    for field, value in defaults.items():
        if field in mapped: mapped[field] = mapped[field].fillna(value)
    if "processing_fee" in mapped: mapped["processing_fee"] = pd.to_numeric(mapped.processing_fee,errors="coerce").fillna(0.0)
    return mapped, issues


def cross_validate(frames: dict[str, pd.DataFrame]) -> list[QualityIssue]:
    issues = []
    players = set(frames.get("players", pd.DataFrame()).get("player_id", pd.Series(dtype=str)).dropna().astype(str))
    for dataset in ("casino_sessions","sportsbook_bets","transactions","bonuses","kyc_risk_events"):
        frame = frames.get(dataset)
        if frame is None or frame.empty or "player_id" not in frame: continue
        orphan_count = int((~frame.player_id.astype(str).isin(players)).sum())
        if orphan_count: issues.append(QualityIssue("ERROR",dataset,"player_id",None,"ORPHAN_PLAYER",f"{orphan_count:,} rows reference players absent from players.csv."))
    campaigns = set(frames.get("campaigns",pd.DataFrame()).get("campaign_id",pd.Series(dtype=str)).dropna().astype(str))
    bonuses = frames.get("bonuses")
    if bonuses is not None and not bonuses.empty and "campaign_id" in bonuses and campaigns:
        values = bonuses.campaign_id.dropna().astype(str); orphan_count = int((~values.isin(campaigns)).sum())
        if orphan_count: issues.append(QualityIssue("WARNING","bonuses","campaign_id",None,"ORPHAN_CAMPAIGN",f"{orphan_count:,} bonuses reference unknown campaigns."))
    games = frames.get("games"); sessions = frames.get("casino_sessions")
    if games is not None and not games.empty and sessions is not None and not sessions.empty and "game_id" in sessions:
        known_games = set(games.game_id.dropna().astype(str)); orphan_count = int((~sessions.game_id.astype(str).isin(known_games)).sum())
        if orphan_count: issues.append(QualityIssue("ERROR","casino_sessions","game_id",None,"ORPHAN_GAME",f"{orphan_count:,} sessions reference games absent from games.csv."))
    return issues


def quality_summary(frames: dict[str,pd.DataFrame], issues: list[QualityIssue]) -> dict:
    errors = sum(issue.severity=="ERROR" for issue in issues); warnings = sum(issue.severity=="WARNING" for issue in issues)
    rows = sum(len(frame) for frame in frames.values()); score = max(0, 100-errors*8-warnings*2)
    return {"rows":rows,"datasets":len(frames),"errors":errors,"warnings":warnings,"score":score,"ready":errors==0 and "players" in frames and any(name in frames for name in ("casino_sessions","sportsbook_bets","transactions"))}


def issues_frame(issues: list[QualityIssue]) -> pd.DataFrame:
    return pd.DataFrame([asdict(issue) for issue in issues], columns=["severity","dataset","column","row","code","message"])


def _fallback_scores(players: pd.DataFrame, scored_at: str) -> pd.DataFrame:
    result = pd.DataFrame({"player_id":players.player_id})
    for field in ["predicted_ltv_90d","churn_probability","churn_probability_7d","churn_probability_14d","churn_probability_30d","observed_value","remaining_ltv_30d","remaining_ltv_90d","remaining_ltv_180d","predicted_total_ltv_30d","predicted_total_ltv_90d","predicted_total_ltv_180d","fraud_risk","rg_risk"]: result[field] = None
    result["recommended_action"]="Missing data"; result["model_confidence"]=None; result["last_session"]=None; result["session_count"]=0; result["lifetime_ggr"]=None; result["model_version"]="unavailable"; result["scored_at"]=scored_at
    return result


def _train_real_models(candidate: Path, run_id: str) -> bool:
    """Train real churn/LTV/forecast/anomaly/NBA models on freshly imported data.

    ml.pipeline trains against fixed calendar snapshots (see ml/shared/features.py
    TEMPORAL_WINDOWS and ml/shared/config.py SCORING_CUTOFF) rather than dates relative
    to the imported file. Real training only runs when the imported history actually
    covers those snapshots, so predictions are either genuinely modelled or explicitly
    "Missing data" — never silently trained on an empty or partial window. Making the
    windows relative to the imported data's own date range is tracked separately.
    """
    from ml.pipeline import train_and_score
    from ml.shared.config import SCORING_CUTOFF
    from ml.shared.features import TEMPORAL_WINDOWS

    required_min = min(cutoff for windows in TEMPORAL_WINDOWS.values() for cutoff in windows["train"])
    with sqlite3.connect(candidate) as conn:
        row = conn.execute("""
            SELECT MIN(d), MAX(d) FROM (
              SELECT DATE(session_start) d FROM sessions
              UNION ALL SELECT DATE(bet_date) FROM sports_bets
              UNION ALL SELECT DATE(transaction_date) FROM transactions
            )
        """).fetchone()
    if not row or row[0] is None or row[1] is None or row[0] > required_min or row[1] < SCORING_CUTOFF:
        return False
    try:
        train_and_score(candidate, IMPORT_ROOT / f"models_{run_id}")
        return True
    except Exception:
        return False


def _registry() -> sqlite3.Connection:
    IMPORT_ROOT.mkdir(parents=True,exist_ok=True); conn=sqlite3.connect(REGISTRY_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS import_runs(run_id TEXT PRIMARY KEY,created_at TEXT,status TEXT,files_json TEXT,rows_loaded INTEGER,quality_score INTEGER,error_count INTEGER,warning_count INTEGER,report_json TEXT)""")
    return conn


def activate_import(frames: dict[str,pd.DataFrame], issues: list[QualityIssue], filenames: list[str]) -> tuple[str,Path]:
    summary=quality_summary(frames,issues)
    if not summary["ready"]: raise ValueError("Import cannot be activated until every blocking quality error is resolved.")
    IMPORT_ROOT.mkdir(parents=True,exist_ok=True); run_id=uuid4().hex[:12]; candidate=IMPORT_ROOT/f"candidate_{run_id}.db"; now=datetime.now(timezone.utc).isoformat()
    core_columns={
        "players":["player_id","registration_date","country","channel","device","vip_level","kyc_status","age_group"],
        "sessions":["session_id","player_id","game_id","session_start","duration_minutes","total_bet_amount","total_payout_amount","casino_ggr","bet_count"],
        "sports_bets":["bet_id","player_id","bet_date","sport","is_live","odds","stake","payout","sportsbook_ggr","event_name"],
        "transactions":["transaction_id","player_id","transaction_date","transaction_type","amount","transaction_status","payment_method","processing_fee"],
    }
    try:
        with sqlite3.connect(candidate) as conn:
            for target, columns in core_columns.items():
                source_name="casino_sessions" if target=="sessions" else "sportsbook_bets" if target=="sports_bets" else target
                frame=frames.get(source_name,pd.DataFrame(columns=columns)).copy()
                for column in columns:
                    if column not in frame: frame[column]=pd.NA
                frame[columns].to_sql(f"raw_{target}",conn,if_exists="replace",index=False)
            sessions=frames.get("casino_sessions",pd.DataFrame())
            games_file=frames.get("games")
            if games_file is not None and not games_file.empty:
                games=games_file[["game_id","game_name","game_family","theoretical_rtp","provider"]].drop_duplicates("game_id").copy()
            elif sessions.empty:
                games=pd.DataFrame(columns=["game_id","game_name","game_family","theoretical_rtp","provider"])
            else:
                games=sessions[["game_id","game_name","game_family","theoretical_rtp","provider"]].drop_duplicates("game_id").copy()
                games.game_name=games.game_name.mask(games.game_name.eq("Unknown"),games.game_id); games.theoretical_rtp=games.theoretical_rtp.fillna(.96)
            games.to_sql("raw_games",conn,if_exists="replace",index=False)
            for name in ("bonuses","campaigns","kyc_risk_events"):
                frames.get(name,pd.DataFrame(columns=CONTRACTS[name].fields)).to_sql(f"raw_{name}",conn,if_exists="replace",index=False)
        build_warehouse(candidate,include_ml=False)
        if not _train_real_models(candidate,run_id):
            with sqlite3.connect(candidate) as conn:
                _fallback_scores(frames["players"],now).to_sql("model_scores",conn,if_exists="replace",index=False)
                pd.DataFrame(columns=["model_name","metric_name","metric_value","model_version","measured_at"]).to_sql("model_metrics",conn,if_exists="replace",index=False)
                pd.DataFrame(columns=["model_name","horizon_days","split","metric_name","metric_value","model_version","measured_at"]).to_sql("model_metrics_v2",conn,if_exists="replace",index=False)
                pd.DataFrame(columns=["metric","forecast_date","actual_value","predicted_value","lower_bound","upper_bound","split","model_version"]).to_sql("forecast_backtest",conn,if_exists="replace",index=False)
                pd.DataFrame(columns=["forecast_date","predicted_revenue","lower_bound","upper_bound","model_version"]).to_sql("revenue_forecast",conn,if_exists="replace",index=False)
                pd.DataFrame(columns=["detected_date","metric","current_value","usual_value","anomaly_score","severity","method","model_version","detected_at"]).to_sql("ml_anomalies",conn,if_exists="replace",index=False)
                pd.DataFrame(columns=["player_id","recommended_action","reason","action_confidence","estimated_value_at_stake","model_version","scored_at"]).to_sql("next_best_actions",conn,if_exists="replace",index=False)
                conn.execute("INSERT OR REPLACE INTO app_metadata VALUES('model_status','unavailable')"); conn.execute("INSERT OR REPLACE INTO app_metadata VALUES('import_run_id',?)",(run_id,)); conn.commit()
        else:
            with sqlite3.connect(candidate) as conn:
                conn.execute("INSERT OR REPLACE INTO app_metadata VALUES('import_run_id',?)",(run_id,)); conn.commit()
        build_warehouse(candidate,include_ml=True)
        if ACTIVE_DB.exists():
            archive=IMPORT_ROOT/f"archive_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.db"; os.replace(ACTIVE_DB,archive)
        os.replace(candidate,ACTIVE_DB)
        status="SUCCESS"
    except Exception:
        status="FAILED"
        if candidate.exists(): candidate.unlink()
        raise
    finally:
        with _registry() as conn:
            conn.execute("INSERT INTO import_runs VALUES(?,?,?,?,?,?,?,?,?)",(run_id,now,status,json.dumps(filenames),summary["rows"],summary["score"],summary["errors"],summary["warnings"],issues_frame(issues).to_json(orient="records")))
    return run_id,ACTIVE_DB


def import_history(limit: int=20) -> pd.DataFrame:
    with _registry() as conn:
        return pd.read_sql_query("SELECT run_id,created_at,status,rows_loaded,quality_score,error_count,warning_count FROM import_runs ORDER BY created_at DESC LIMIT ?",conn,params=(limit,))


def active_database() -> Path | None:
    return ACTIVE_DB if ACTIVE_DB.exists() else None


def file_fingerprint(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:12]
