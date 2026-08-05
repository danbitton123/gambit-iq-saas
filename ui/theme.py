from __future__ import annotations

import streamlit as st


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@500;600;700&display=swap');
:root { --bg:#050f1c; --panel:#071c24; --line:#173b43; --gold:#d9a72e; --green:#27d17f; --muted:#8da3b4; }
.stApp { background: radial-gradient(circle at 80% -10%, #0b2633 0, #050f1c 34%, #030914 100%); color:#f4f7fb; }
html, body, [class*="css"] { font-family:'Inter',sans-serif; }
h1,h2,h3 { font-family:'Manrope',sans-serif !important; letter-spacing:-.02em; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#061625 0%,#04101c 100%); border-right:1px solid rgba(217,167,46,.32); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#d8e2ea; }
[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(9,48,48,.88),rgba(5,26,35,.96)); border:1px solid rgba(39,209,127,.28); border-radius:14px; padding:16px 18px; min-height:118px; box-shadow:0 12px 30px rgba(0,0,0,.16); }
[data-testid="stMetricLabel"] { color:#9eb0bc; font-weight:600; }
[data-testid="stMetricValue"] { font-family:'Manrope',sans-serif; font-weight:700; }
[data-testid="stMetricDelta"] { font-weight:600; }
.block-container { max-width:1700px; padding-top:1.1rem; padding-bottom:3rem; }
.gambit-brand { border:1px solid rgba(217,167,46,.4); border-radius:18px; padding:18px 14px; text-align:center; margin:4px 0 20px; background:linear-gradient(145deg,rgba(217,167,46,.10),rgba(4,16,28,.2)); }
.brand-coin { width:58px;height:58px;border-radius:50%;margin:auto;border:3px double #d9a72e;display:grid;place-items:center;color:#d9a72e;font:700 28px Manrope;box-shadow:0 0 24px rgba(217,167,46,.16); }
.brand-name { color:#e8c15f;font:700 20px Manrope;letter-spacing:.12em;margin-top:9px; }
.eyebrow { color:#d9a72e;font-size:.74rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:5px; }
.page-title { font:700 2rem Manrope;margin:0;color:#f6f8fb; }
.page-subtitle { color:#8da3b4;margin:3px 0 18px;font-size:.96rem; }
.live-pill { display:inline-flex;gap:7px;align-items:center;border:1px solid rgba(39,209,127,.4);background:rgba(39,209,127,.08);color:#76e8ad;padding:7px 11px;border-radius:9px;font-size:.78rem;font-weight:600; }
.live-dot {width:7px;height:7px;border-radius:50%;background:#27d17f;box-shadow:0 0 8px #27d17f;}
.panel-title { color:#ecf2f6;font:600 .82rem Manrope;letter-spacing:.04em;text-transform:uppercase;margin:0; }
.insight-card { border:1px solid rgba(217,167,46,.30); background:linear-gradient(145deg,rgba(16,38,44,.95),rgba(6,20,29,.96)); padding:14px;border-radius:12px;margin:7px 0; }
.insight-card strong {color:#f7f8fa}.insight-card small {color:#8da3b4}.impact {color:#27d17f;font-weight:700}.risk {color:#ff6b65;font-weight:700}
.status-good {color:#27d17f}.status-warn {color:#f5b84b}.status-bad {color:#ff5b57}
div[data-testid="stDataFrame"] { border:1px solid rgba(141,163,180,.16);border-radius:12px;overflow:hidden; }
.stPlotlyChart { background:linear-gradient(145deg,rgba(7,28,36,.74),rgba(5,18,28,.88));border:1px solid rgba(141,163,180,.14);border-radius:14px;padding:6px; }
button[kind="primary"] {background:linear-gradient(90deg,#0b8056,#16a56f)!important;border:0!important;}
hr {border-color:rgba(141,163,180,.12)!important}
[data-testid="stSidebar"] div[role="radiogroup"] label { padding:.48rem .6rem;border-radius:9px;margin:2px 0; }
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background:linear-gradient(90deg,rgba(217,167,46,.18),rgba(39,209,127,.08));border-left:2px solid #d9a72e; }
@media (max-width: 768px) {
  .block-container { padding: .75rem .7rem 2rem; }
  .page-title { font-size:1.42rem; }
  .page-subtitle { font-size:.82rem; margin-bottom:12px; }
  .live-pill { font-size:.68rem; padding:5px 8px; }
  [data-testid="stMetric"] { min-height:96px; padding:12px; }
  [data-testid="stMetricValue"] { font-size:1.45rem; }
  .stPlotlyChart { padding:2px; border-radius:10px; }
}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def brand() -> None:
    st.sidebar.markdown(
        "<div class='gambit-brand'><div class='brand-coin'>G</div><div class='brand-name'>GAMBIT IQ</div></div>",
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, eyebrow: str = "Intelligence Platform") -> None:
    left, right = st.columns([8, 2])
    with left:
        st.markdown(
            f"<div class='eyebrow'>{eyebrow}</div><div class='page-title'>{title}</div><div class='page-subtitle'>{subtitle}</div>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("<div style='height:20px'></div><div class='live-pill'><span class='live-dot'></span> LIVE · Updated 09:00</div>", unsafe_allow_html=True)
