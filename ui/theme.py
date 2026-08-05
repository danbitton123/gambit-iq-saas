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
[data-testid="stSidebarNav"] { padding-bottom:.45rem; border-bottom:1px solid rgba(141,163,180,.12); }
[data-testid="stSidebarNav"] span { font-weight:600; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background:linear-gradient(90deg,rgba(217,167,46,.20),rgba(39,209,127,.10)); border-left:3px solid #d9a72e; color:#f4f7fb; }
[data-testid="stSidebarCollapseButton"] button, [data-testid="stExpandSidebarButton"] button { border:1px solid rgba(217,167,46,.35); background:#071c24; color:#e8c15f; border-radius:9px; }
[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(9,48,48,.88),rgba(5,26,35,.96)); border:1px solid rgba(39,209,127,.28); border-radius:14px; padding:16px 18px; min-height:118px; box-shadow:0 12px 30px rgba(0,0,0,.16); }
[data-testid="stMetricLabel"] { color:#9eb0bc; font-weight:600; }
[data-testid="stMetricValue"] { font-family:'Manrope',sans-serif; font-weight:700; }
[data-testid="stMetricDelta"] { font-weight:600; }
.block-container { max-width:1700px; padding-top:1.1rem; padding-bottom:3rem; }
.eyebrow { color:#d9a72e;font-size:.74rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:5px; }
.page-title { font:700 2rem Manrope;margin:0;color:#f6f8fb; }
.page-subtitle { color:#8da3b4;margin:3px 0 18px;font-size:.96rem; }
.live-pill { display:inline-flex;gap:7px;align-items:center;border:1px solid rgba(39,209,127,.4);background:rgba(39,209,127,.08);color:#76e8ad;padding:7px 11px;border-radius:9px;font-size:.78rem;font-weight:600; }
.live-dot {width:7px;height:7px;border-radius:50%;background:#27d17f;box-shadow:0 0 8px #27d17f;}
.filter-summary { display:flex;flex-direction:column;gap:3px;border:1px solid rgba(38,198,229,.22);background:rgba(38,198,229,.06);padding:10px 11px;border-radius:10px;margin-bottom:12px; }
.filter-summary span { color:#8da3b4;font-size:.64rem;font-weight:700;letter-spacing:.13em; }
.filter-summary strong { color:#f4f7fb;font:600 .86rem Manrope; }
.filter-summary small { color:#9eb0bc;font-size:.72rem; }
.panel-title { color:#ecf2f6;font:600 .82rem Manrope;letter-spacing:.04em;text-transform:uppercase;margin:0; }
.insight-card { border:1px solid rgba(217,167,46,.30); background:linear-gradient(145deg,rgba(16,38,44,.95),rgba(6,20,29,.96)); padding:14px;border-radius:12px;margin:7px 0; }
.insight-card strong {color:#f7f8fa}.insight-card small {color:#8da3b4}.impact {color:#27d17f;font-weight:700}.risk {color:#ff6b65;font-weight:700}
.status-good {color:#27d17f}.status-warn {color:#f5b84b}.status-bad {color:#ff5b57}
div[data-testid="stDataFrame"] { border:1px solid rgba(141,163,180,.16);border-radius:12px;overflow:hidden; }
.stPlotlyChart { background:linear-gradient(145deg,rgba(7,28,36,.74),rgba(5,18,28,.88));border:1px solid rgba(141,163,180,.14);border-radius:14px;padding:6px; }
.app-state { display:flex;gap:13px;align-items:flex-start;border:1px solid rgba(141,163,180,.25);border-left:4px solid #26c6e5;background:rgba(7,28,36,.84);padding:15px 17px;border-radius:12px;margin:12px 0 18px; }
.app-state-icon { width:25px;height:25px;flex:0 0 25px;border-radius:50%;display:grid;place-items:center;background:rgba(38,198,229,.14);font-weight:800; }
.app-state strong { font:600 .94rem Manrope;color:#f4f7fb; }.app-state p { margin:3px 0;color:#b6c5cf;font-size:.86rem; }.app-state small { color:#8da3b4; }
.app-state-error { border-left-color:#ff5b57; }.app-state-warning { border-left-color:#f5b84b; }.app-state-success { border-left-color:#27d17f; }
.element-container { max-width:100%; }
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
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:.65rem; }
  [data-testid="column"] { min-width:100% !important; flex:1 1 100% !important; }
  [data-testid="stDataFrame"] { overflow-x:auto; }
  .gambit-brand { padding:12px 10px; margin-bottom:12px; }
  .brand-coin { width:44px;height:44px;font-size:22px; }
  .brand-name { font-size:16px; }
}
</style>
"""


LIGHT_CSS = """
<style>
.stApp { background:radial-gradient(circle at 80% -10%,#e8f5f4 0,#f5f7fa 38%,#eef2f6 100%);color:#13232d; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#ffffff 0%,#edf3f6 100%);border-right:1px solid #d6b761; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,[data-testid="stSidebar"] label { color:#263b47; }
[data-testid="stSidebarNavLink"][aria-current="page"] { color:#10242d;background:linear-gradient(90deg,rgba(217,167,46,.25),rgba(39,209,127,.12)); }
h1,h2,h3,.page-title,.panel-title { color:#112731!important; }.page-subtitle { color:#5c7080; }
[data-testid="stMetric"] { background:linear-gradient(145deg,#ffffff,#edf7f4);border-color:rgba(11,128,86,.22);box-shadow:0 8px 24px rgba(25,48,60,.08); }
[data-testid="stMetricLabel"] { color:#5c7080; }[data-testid="stMetricValue"] { color:#112731; }
.filter-summary { background:#eef8fa; }.filter-summary strong { color:#18313c; }.filter-summary span,.filter-summary small { color:#5c7080; }
.insight-card,.app-state { background:linear-gradient(145deg,#ffffff,#f2f6f7);color:#18313c; }.insight-card strong,.app-state strong { color:#18313c; }.insight-card small,.app-state p,.app-state small { color:#5c7080; }
.stPlotlyChart { background:linear-gradient(145deg,#ffffff,#f6f9fa);border-color:#dbe4e9; }
[data-baseweb="select"] > div,[data-testid="stDateInput"] input { background:#ffffff!important;color:#18313c!important; }
</style>
"""


def apply_theme(mode: str = "Dark") -> None:
    st.markdown(CSS + (LIGHT_CSS if mode == "Light" else ""), unsafe_allow_html=True)


def page_header(title: str, subtitle: str, eyebrow: str = "Intelligence Platform") -> None:
    left, right = st.columns([8, 2])
    with left:
        st.markdown(
            f"<div class='eyebrow'>{eyebrow}</div><div class='page-title'>{title}</div><div class='page-subtitle'>{subtitle}</div>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("<div style='height:20px'></div><div class='live-pill'><span class='live-dot'></span> FILTERED VIEW</div>", unsafe_allow_html=True)
