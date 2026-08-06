from __future__ import annotations

import os
from uuid import uuid4

import plotly.express as px
import streamlit as st

from config import COLORS
from data.copilot import CopilotResponse, GovernedCopilot
from data.decision_engine import DecisionEngine
from ui.charts import PALETTE, polish


PAGE_QUESTIONS = {
    "Command Center": ("What are the five priority actions?", "Explain this page", "Why did NGR change?"),
    "Forecast & Recommendations": ("Why did NGR change?", "What are the five priority actions?", "Explain this page"),
    "Player Intelligence": ("Which VIP players need attention?", "How much value is at risk from churn?", "Explain this page"),
    "Player Profile": ("Which VIP players need attention?", "Explain this page", "How much value is at risk from churn?"),
    "CRM Automation": ("How much value is at risk from churn?", "Which VIP players need attention?", "Explain this page"),
    "Casino": ("Show me casino performance", "Which games are underperforming?", "Explain this chart"),
    "Sportsbook": ("Show me sportsbook performance", "What should I focus on here?", "Explain this page"),
    "Acquisition": ("Which channels should receive more budget?", "What should I focus on here?", "Explain these KPIs"),
    "Revenue & Finance": ("Why did NGR change?", "Show me payment performance", "Explain this page"),
    "Risk & Compliance": ("Which VIP players require attention?", "How much value is at risk from churn?", "Explain this page"),
    "Data Import Studio": ("Explain this page", "Show me payment performance", "What data is missing?"),
    "AI Copilot": ("What are the five priority actions?", "Why did NGR change?", "Which games are underperforming?"),
}


def build_copilot_figure(response: CopilotResponse, compact: bool = False):
    spec = response.chart
    if spec is None or response.evidence.empty:
        return None
    data = response.evidence.copy()
    if spec.kind == "bar":
        fig = px.bar(data, x=spec.x, y=list(spec.y), barmode="group", title=spec.title,
                     color_discrete_sequence=PALETTE)
    else:
        fig = px.line(data, x=spec.x, y=list(spec.y), title=spec.title,
                      color_discrete_sequence=PALETTE)
    fig.update_layout(coloraxis_showscale=False)
    return polish(fig, 270 if compact else 370, legend=len(spec.y) > 1)


def render_copilot_visual(response: CopilotResponse, compact: bool = False) -> None:
    figure = build_copilot_figure(response, compact)
    if figure is None:
        return
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True},
                    key=f"copilot_chart_{uuid4().hex}")
    st.caption(response.chart.explanation)


def _submit_question(ctx, page: str, question: str) -> None:
    history = st.session_state.setdefault("floating_copilot_history", [])
    previous_response=history[-1]["response"] if history else None
    previous_intent=previous_response.intent if previous_response else None
    alerts = DecisionEngine(ctx).evaluate()
    response=GovernedCopilot(ctx,alerts).ask(question,previous_intent=previous_intent,page_context=page,previous_response=previous_response)
    history.append({"question": question, "response": response, "page": page, "scope": ctx.period_label})
    st.session_state["floating_copilot_history"] = history[-8:]


def render_floating_assistant(ctx, page: str) -> None:
    st.session_state.setdefault("floating_copilot_history", [])
    with st.container(key="floating_ai_assistant"):
        with st.popover("Ask CasinoAI", icon=":material/auto_awesome:", width="stretch"):
            mode = "Conversational AI" if os.getenv("OPENAI_API_KEY") else "Governed analytics"
            st.markdown(
                f"<div class='floating-ai-head'><span class='material-symbols-rounded'>neurology</span>"
                f"<div><small>{mode.upper()}</small><strong>How can I help?</strong>"
                f"<p>{page} · {ctx.country}</p></div></div>", unsafe_allow_html=True,
            )
            suggestions = PAGE_QUESTIONS.get(page, PAGE_QUESTIONS["Command Center"])
            st.caption("Ask about this page, a KPI, a chart or the underlying business signal.")
            for index, suggestion in enumerate(suggestions):
                if st.button(suggestion, key=f"floating_suggestion_{page}_{index}", width="stretch"):
                    _submit_question(ctx, page, suggestion)
                    st.rerun()
            with st.form("floating_copilot_form", clear_on_submit=True):
                question = st.text_input("Your question", placeholder="Why did this KPI change?", label_visibility="collapsed")
                sent = st.form_submit_button("Ask the data", icon=":material/arrow_upward:", width="stretch")
            if sent and question.strip():
                _submit_question(ctx, page, question.strip())
                st.rerun()

            history = st.session_state.floating_copilot_history
            if history:
                st.divider()
                for item in reversed(history[-3:]):
                    with st.chat_message("user"): st.write(item["question"])
                    with st.chat_message("assistant"):
                        response = item["response"]
                        st.warning(response.answer, icon=":material/shield:") if response.refused else st.write(response.answer)
                        render_copilot_visual(response, compact=True)
                        st.caption(f"{response.confidence:.0%} confidence · {item['scope']}")
                        with st.expander("Sources and limits"):
                            for source in response.sources: st.caption(f"↳ {source}")
                            st.caption(response.limitations)
                if st.button("Clear conversation", icon=":material/delete_sweep:", key="floating_clear", width="stretch"):
                    st.session_state.floating_copilot_history = []
                    st.rerun()
