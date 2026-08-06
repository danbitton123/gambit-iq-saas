from __future__ import annotations

import pandas as pd

from data.repository import SQLContext, get_repository
from data.semantic_query import DATASETS, SemanticQueryEngine


def _context():
    repo=get_repository()
    return SQLContext(repo,pd.Timestamp("2026-05-07"),pd.Timestamp("2026-08-04"),"All markets")


def test_open_revenue_question_returns_country_insight_and_chart_data():
    result=SemanticQueryEngine(_context()).answer("What is the revenue per country?")
    assert result is not None and not result.evidence.empty
    assert list(result.evidence.columns)==["Country","Observed GGR"]
    assert result.chart_x=="Country" and result.chart_y==("Observed GGR",)
    assert result.evidence["Observed GGR"].is_monotonic_decreasing


def test_semantic_layer_handles_cross_domain_breakdowns():
    engine=SemanticQueryEngine(_context())
    questions={
        "How many players per country?":"Observed Players",
        "Which payment method has the most deposits?":"Observed Approved Deposits",
        "Show monthly casino GGR":"Observed Casino GGR",
        "Top 5 sports by handle":"Observed Handle",
    }
    for question,metric in questions.items():
        result=engine.answer(question)
        assert result is not None and metric in result.evidence.columns
        assert len(result.evidence)<=100


def test_unrelated_question_cannot_reach_the_warehouse():
    assert SemanticQueryEngine(_context()).answer("Who will win the next election?") is None
    assert all(spec.table for spec in DATASETS.values())
