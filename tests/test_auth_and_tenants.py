from __future__ import annotations

import sqlite3
from io import BytesIO

import pandas as pd
import pytest

import auth.service as auth_service
import data.tenant as tenant
from auth.service import AuthError
from data.repository import get_repository
from data.tenant import ImportValidationError, ingest_excel_workbooks, parse_excel_files, tenant_db_path
from ui.components import money, number, pct


class Upload:
    def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload

    def getvalue(self) -> bytes:
        return self._payload


@pytest.fixture()
def isolated_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_service, "USERS_DB_PATH", tmp_path / "users.db")
    monkeypatch.setattr(tenant, "TENANT_ROOT", tmp_path / "tenants")
    return tmp_path


def _workbook(players: pd.DataFrame, transactions: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        players.to_excel(writer, sheet_name="players", index=False)
        transactions.to_excel(writer, sheet_name="transactions", index=False)
    return buffer.getvalue()


def _players(*ids: str) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "player_id": player_id,
            "registration_date": "2026-07-01",
            "country": "UK",
            "channel": "Organic",
            "device": "Mobile",
            "vip_level": "None",
            "kyc_status": "Verified",
            "age_group": "25-34",
        }
        for player_id in ids
    ])


def _transactions(player_id: str, amount: float) -> pd.DataFrame:
    return pd.DataFrame([{
        "transaction_id": f"TX-{player_id}",
        "player_id": player_id,
        "transaction_date": "2026-08-01",
        "transaction_type": "Deposit",
        "amount": amount,
        "transaction_status": "Approved",
        "payment_method": "Card",
        "processing_fee": 1.25,
    }])


def test_email_accounts_are_hashed_and_isolated(isolated_accounts):
    alice = auth_service.register_email("Alice@Example.com", "StrongPass1", "Alice Smith")
    bob = auth_service.register_email("bob@example.com", "AnotherPass2", "Bob Jones")

    assert auth_service.authenticate_email("alice@example.com", "StrongPass1").user_id == alice.user_id
    assert alice.user_id != bob.user_id
    assert tenant_db_path(alice.user_id) != tenant_db_path(bob.user_id)
    with sqlite3.connect(auth_service.USERS_DB_PATH) as connection:
        stored_hash, stored_salt = connection.execute(
            "SELECT password_hash,password_salt FROM users WHERE user_id=?", (alice.user_id,)
        ).fetchone()
    assert stored_hash != "StrongPass1"
    assert stored_salt and len(stored_hash) == 64
    with pytest.raises(AuthError, match="Invalid email or password"):
        auth_service.authenticate_email("alice@example.com", "wrong")


def test_two_different_excel_datasets_remain_distinct(isolated_accounts):
    alice = auth_service.register_email("alice@example.com", "StrongPass1", "Alice Smith")
    bob = auth_service.register_email("bob@example.com", "AnotherPass2", "Bob Jones")
    alice_upload = Upload("alice.xlsx", _workbook(_players("A-1"), _transactions("A-1", 125.0)))
    bob_upload = Upload("bob.xlsx", _workbook(_players("B-1", "B-2"), _transactions("B-1", 800.0)))

    alice_frames, alice_manifest = parse_excel_files([alice_upload])
    bob_frames, bob_manifest = parse_excel_files([bob_upload])

    assert alice_manifest["players"] == 1
    assert bob_manifest["players"] == 2
    assert alice_frames["transactions"].iloc[0]["amount"] == 125.0
    assert bob_frames["transactions"].iloc[0]["amount"] == 800.0
    assert tenant_db_path(alice.user_id).parent != tenant_db_path(bob.user_id).parent

    alice_path, _, alice_models = ingest_excel_workbooks(alice.user_id, [alice_upload])
    bob_path, _, bob_models = ingest_excel_workbooks(bob.user_id, [bob_upload])
    alice_repo = get_repository(str(alice_path))
    bob_repo = get_repository(str(bob_path))
    assert alice_repo.query("SELECT COUNT(*) AS n FROM dim_player").iloc[0]["n"] == 1
    assert bob_repo.query("SELECT COUNT(*) AS n FROM dim_player").iloc[0]["n"] == 2
    assert alice_repo.query("SELECT SUM(amount) AS amount FROM fact_transaction").iloc[0]["amount"] == 125.0
    assert bob_repo.query("SELECT SUM(amount) AS amount FROM fact_transaction").iloc[0]["amount"] == 800.0
    assert alice_models == bob_models == "unavailable"
    assert not alice_repo.model_available()


def test_invalid_and_missing_excel_data_are_explicit():
    empty = Upload("unknown.xlsx", _workbook(pd.DataFrame(), pd.DataFrame()))
    with pytest.raises(ImportValidationError):
        parse_excel_files([empty])
    assert money(None) == "Missing data"
    assert pct(float("nan")) == "Missing data"
    assert number(None) == "Missing data"
