from __future__ import annotations
import sqlite3
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data.generator import build_games,build_players,build_sessions,build_sports_bets,build_transactions,generate_database
from ml.pipeline import train_and_score
from data.warehouse import build_warehouse

def test_generated_data_is_consistent():
    rng=np.random.default_rng(11);players=build_players(rng,250);games=build_games();sessions=build_sessions(rng,players,games,1000);transactions=build_transactions(rng,players,500);sports=build_sports_bets(rng,players,600)
    assert sessions.player_id.isin(players.player_id).all();assert sessions.game_id.isin(games.game_id).all();assert transactions.player_id.isin(players.player_id).all();assert sports.player_id.isin(players.player_id).all()

def test_sql_warehouse_and_ml_scores(tmp_path):
    db=tmp_path/"test.db";generate_database(db);report=train_and_score(db,tmp_path/"models");build_warehouse(db,include_ml=True)
    with sqlite3.connect(db) as conn:
        players=conn.execute("SELECT COUNT(*) FROM players WHERE registration_date<='2026-06-30 23:59:59'").fetchone()[0]
        scores=conn.execute("SELECT COUNT(*) FROM model_scores").fetchone()[0]
        invalid=conn.execute("SELECT COUNT(*) FROM model_scores WHERE churn_probability NOT BETWEEN 0 AND 1 OR fraud_risk NOT BETWEEN 0 AND 1 OR rg_risk NOT BETWEEN 0 AND 1").fetchone()[0]
        metrics=conn.execute("SELECT COUNT(DISTINCT model_name) FROM model_metrics").fetchone()[0]
        views=conn.execute("SELECT COUNT(*) FROM v_sessions_enriched").fetchone()[0]
        mart_players=conn.execute("SELECT COUNT(*) FROM mart_player_360").fetchone()[0]
    assert report["rows"]==players==scores==mart_players;assert invalid==0;assert metrics==5;assert views>0
