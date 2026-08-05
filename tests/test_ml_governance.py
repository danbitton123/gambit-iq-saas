from __future__ import annotations

import sqlite3

from data.generator import generate_database
from ml.pipeline import MODEL_VERSION, TEMPORAL_WINDOWS, train_and_score


def test_temporal_windows_are_strictly_ordered():
    for windows in TEMPORAL_WINDOWS.values():
        assert max(windows["train"]) < min(windows["validation"])
        assert max(windows["validation"]) < min(windows["test"])


def test_advanced_ml_outputs_are_governed(tmp_path):
    database = tmp_path / "ml.db"
    generate_database(database)
    report = train_and_score(database, tmp_path / "models")
    with sqlite3.connect(database) as connection:
        splits = {row[0] for row in connection.execute("SELECT DISTINCT split FROM model_metrics_v2")}
        horizons = {row[0] for row in connection.execute("SELECT DISTINCT horizon_days FROM model_metrics_v2 WHERE horizon_days IS NOT NULL")}
        forecast_targets = {row[0] for row in connection.execute("SELECT DISTINCT metric FROM forecast_backtest")}
        actions = {row[0] for row in connection.execute("SELECT DISTINCT recommended_action FROM next_best_actions")}
        invalid = connection.execute("""SELECT COUNT(*) FROM model_scores WHERE
            churn_probability_7d NOT BETWEEN 0 AND 1 OR churn_probability_14d NOT BETWEEN 0 AND 1
            OR churn_probability_30d NOT BETWEEN 0 AND 1""").fetchone()[0]
    assert report["model_version"] == MODEL_VERSION
    assert splits == {"validation", "test"}
    assert {7, 14, 30, 90, 180} <= horizons
    assert forecast_targets == {"ggr", "ngr", "deposits", "ftd", "casino_ggr", "sportsbook_ggr"}
    assert "Do nothing" in actions and len(actions) >= 4
    assert invalid == 0
