from __future__ import annotations

import sqlite3

import pandas as pd
from pathlib import Path
from streamlit.testing.v1 import AppTest

import data.importer as importer


def _players():
    return pd.DataFrame([{ "customer_id":"P1","signup_date":"2026-01-01","market":"Canada","source":"Organic" }])


def _transactions():
    return pd.DataFrame([{ "payment_id":"T1","customer_id":"P1","created_at":"2026-01-02","type":"Deposit","value":"100.50","status":"Approved","method":"Visa" }])


def test_alias_mapping_and_type_validation():
    source=_players(); mapping=importer.suggest_mapping("players",source.columns)
    frame,issues=importer.validate_frame("players",source,mapping)
    assert frame.iloc[0].player_id=="P1"
    assert pd.api.types.is_datetime64_any_dtype(frame.registration_date)
    assert not [issue for issue in issues if issue.severity=="ERROR"]

    bad=_transactions(); bad.loc[0,"value"]="not-a-number"
    _,issues=importer.validate_frame("transactions",bad,importer.suggest_mapping("transactions",bad.columns))
    assert any(issue.code=="INVALID_TYPE" for issue in issues)


def test_duplicates_missing_values_and_orphans_are_blocking():
    source=pd.concat([_players(),_players()],ignore_index=True); source.loc[1,"market"]=None
    frame,issues=importer.validate_frame("players",source,importer.suggest_mapping("players",source.columns))
    assert {issue.code for issue in issues}>={"DUPLICATE_KEY","MISSING_VALUE"}
    transactions=_transactions(); transactions.loc[0,"customer_id"]="UNKNOWN"
    tx,_=importer.validate_frame("transactions",transactions,importer.suggest_mapping("transactions",transactions.columns))
    assert any(issue.code=="ORPHAN_PLAYER" for issue in importer.cross_validate({"players":frame,"transactions":tx}))


def test_valid_csv_activates_atomically_and_records_history(tmp_path,monkeypatch):
    root=tmp_path/"imports"
    monkeypatch.setattr(importer,"IMPORT_ROOT",root); monkeypatch.setattr(importer,"ACTIVE_DB",root/"active.db"); monkeypatch.setattr(importer,"REGISTRY_DB",root/"registry.db")
    players,pissues=importer.validate_frame("players",_players(),importer.suggest_mapping("players",_players().columns))
    transactions,tissues=importer.validate_frame("transactions",_transactions(),importer.suggest_mapping("transactions",_transactions().columns))
    frames={"players":players,"transactions":transactions}; issues=pissues+tissues+importer.cross_validate(frames)
    summary=importer.quality_summary(frames,issues)
    assert summary["ready"] and summary["errors"]==0
    run_id,path=importer.activate_import(frames,issues,["players.csv","transactions.csv"])
    assert path.exists() and run_id
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM dim_player").fetchone()[0]==1
        assert connection.execute("SELECT COUNT(*) FROM fact_transaction").fetchone()[0]==1
        assert connection.execute("SELECT value FROM app_metadata WHERE key='model_status'").fetchone()[0]=="unavailable"
    history=importer.import_history(); assert history.iloc[0].status=="SUCCESS"


def test_csv_parser_detects_delimiter_and_dataset():
    payload=b"customer_id;signup_date;market\nP1;2026-01-01;Canada\n"
    frame=importer.read_csv_payload("client_players.csv",payload)
    assert list(frame.columns)==["customer_id","signup_date","market"]
    assert importer.infer_dataset("client_players.csv",frame.columns)=="players"


def test_import_studio_renders_all_workflow_sections():
    app=AppTest.from_file(Path(__file__).parent/"import_harness.py",default_timeout=30).run()
    assert not app.exception
    assert [tab.label for tab in app.tabs]==["1 · Upload & map","2 · Quality report","3 · Run history","Connector roadmap"]
    assert next(uploader for uploader in app.get("file_uploader") if uploader.label=="Client CSV files")
    html="\n".join(str(item.value) for item in app.markdown)
    assert "CSV PILOT CONNECTOR" in html and "PostgreSQL / MySQL" in html and "Amazon S3" in html
