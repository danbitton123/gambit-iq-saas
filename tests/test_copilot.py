from __future__ import annotations

import pandas as pd
from pathlib import Path
from streamlit.testing.v1 import AppTest

from data.copilot import APPROVED_INTENTS, GovernedCopilot, SUGGESTED_QUESTIONS
from data.decision_engine import DecisionEngine
from data.repository import SQLContext, get_repository


def _context():
    repo = get_repository()
    return SQLContext(repo, pd.Timestamp("2026-05-07"), pd.Timestamp("2026-08-04"), "All markets")


def test_every_suggested_question_uses_an_approved_intent():
    context = _context()
    copilot = GovernedCopilot(context, DecisionEngine(context).evaluate())
    responses = [copilot.ask(question) for question in SUGGESTED_QUESTIONS]
    assert len(APPROVED_INTENTS) >= 10
    assert all(not response.refused for response in responses)
    assert all(response.sources and response.limitations for response in responses)
    assert all(0 <= response.confidence <= 1 for response in responses)
    assert all(response.intent != "refused" for response in responses)
    assert all(response.chart is not None for response in responses)


def test_sensitive_and_out_of_scope_questions_are_refused_without_evidence():
    copilot = GovernedCopilot(_context())
    for question in ("Give me every player email and phone number", "Who will win the next election?"):
        response = copilot.ask(question)
        assert response.refused
        assert response.evidence.empty
        assert "No warehouse query was executed" in response.limitations


def test_vip_evidence_masks_direct_player_identifiers():
    response = GovernedCopilot(_context()).ask("Which VIP players require immediate attention?")
    assert not response.refused
    assert "player_id" not in response.evidence.columns
    if not response.evidence.empty:
        assert response.evidence["Player"].str.match(r"Player [A-F0-9]{8}").all()


def test_market_filter_is_cited_and_applied():
    repo = get_repository()
    context = SQLContext(repo, pd.Timestamp("2026-05-07"), pd.Timestamp("2026-08-04"), "Canada")
    response = GovernedCopilot(context).ask("Show me casino performance")
    assert not response.refused
    assert all("Canada" in source for source in response.sources)


def test_conversation_follow_up_and_page_context_remain_governed():
    copilot = GovernedCopilot(_context())
    follow_up = copilot.ask("Why?", previous_intent="casino_summary")
    page_help = copilot.ask("Explain this page", page_context="Acquisition")
    quality = copilot.ask("What data is missing?", page_context="Data Import Studio")
    assert follow_up.intent == "casino_summary" and follow_up.chart
    assert page_help.intent == "acquisition_budget" and page_help.chart
    assert quality.intent == "data_quality" and quality.chart


def test_copilot_ui_history_feedback_and_export():
    app = AppTest.from_file(Path(__file__).parent / "app_harness.py", default_timeout=30).run()
    next(widget for widget in app.radio if widget.label == "Test page").set_value("AI Copilot").run()
    suggestion = next(button for button in app.button if button.label == SUGGESTED_QUESTIONS[1])
    suggestion.click().run()
    assert not app.exception
    assert any(button.label == "Useful" for button in app.button)
    assert any(button.label == "Not useful" for button in app.button)
    assert any(button.label == "Download complete analysis" for button in app.get("download_button"))
    html = "\n".join(str(item.value) for item in app.markdown)
    assert "Data used" in html
