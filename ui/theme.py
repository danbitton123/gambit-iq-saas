from __future__ import annotations

import streamlit as st


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@500;600;700&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0,0&display=swap');
:root { --bg:#050f1c; --panel:#071c24; --line:#173b43; --gold:#d9a72e; --green:#27d17f; --muted:#8da3b4; }
.material-symbols-rounded { font-family:'Material Symbols Rounded'!important;font-weight:normal;font-style:normal;line-height:1;letter-spacing:normal;text-transform:none;display:inline-block;white-space:nowrap;word-wrap:normal;direction:ltr;-webkit-font-feature-settings:'liga';-webkit-font-smoothing:antialiased;font-feature-settings:'liga'; }
.stApp { background: radial-gradient(circle at 80% -10%, #0b2633 0, #050f1c 34%, #030914 100%); color:#f4f7fb; }
html, body, [class*="css"] { font-family:'Inter',sans-serif; }
h1,h2,h3 { font-family:'Manrope',sans-serif !important; letter-spacing:-.02em; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#061625 0%,#04101c 100%); border-right:1px solid rgba(217,167,46,.32); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#d8e2ea; }
[data-testid="stSidebarNav"] { padding-bottom:.45rem; border-bottom:1px solid rgba(141,163,180,.12); }
[data-testid="stSidebarNav"] span { font-weight:600; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background:linear-gradient(90deg,rgba(217,167,46,.20),rgba(39,209,127,.10)); border-left:3px solid #d9a72e; color:#f4f7fb; }
[data-testid="stSidebarCollapseButton"] button, [data-testid="stExpandSidebarButton"] button { border:1px solid rgba(217,167,46,.35); background:#071c24; color:#e8c15f; border-radius:9px; }
[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(9,48,48,.88),rgba(5,26,35,.96)); border:1px solid rgba(39,209,127,.28); border-radius:14px; padding:17px 18px; min-height:154px; box-shadow:0 12px 30px rgba(0,0,0,.16);overflow:visible; }
[data-testid="stMetricLabel"] { color:#9eb0bc;font-weight:600;min-height:2.65rem;height:auto!important;width:100%;align-items:flex-start;overflow:visible!important; }
[data-testid="stMetricLabel"] > div { width:100%;overflow:visible!important; }[data-testid="stMetricLabel"] p { white-space:normal!important;overflow:visible!important;text-overflow:clip!important;overflow-wrap:anywhere;line-height:1.25!important;font-size:.82rem!important; }
[data-testid="stMetricValue"] { font-family:'Manrope',sans-serif;font-weight:700;font-size:clamp(1.55rem,2.15vw,2.55rem)!important;line-height:1.08!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important;overflow-wrap:anywhere; }
[data-testid="stMetricDelta"] { font-weight:600;max-width:100%;height:auto!important;white-space:normal!important;overflow:visible!important; }
[data-testid="stMetricDelta"] > div,[data-testid="stMetricDelta"] p { white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.22!important;font-size:.76rem!important; }
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
.command-alert { min-height:176px;border:1px solid rgba(141,163,180,.18);border-top:3px solid #27d17f;background:linear-gradient(145deg,rgba(10,39,48,.96),rgba(5,24,33,.98));padding:15px 16px;border-radius:13px;margin:6px 0 12px;box-shadow:0 12px 28px rgba(0,0,0,.12); }
.command-alert-warning { border-top-color:#f5b84b; }.command-alert-critical { border-top-color:#ff5b57; }
.command-alert-top { display:flex;flex-direction:column;gap:5px; }.command-alert-top span { width:max-content;color:#76e8ad;background:rgba(39,209,127,.1);border-radius:5px;padding:3px 7px;font-size:.59rem;font-weight:800;letter-spacing:.12em; }
.command-alert-warning .command-alert-top span { color:#f5c76b;background:rgba(245,184,75,.12); }.command-alert-critical .command-alert-top span { color:#ff8d89;background:rgba(255,91,87,.12); }
.command-alert-top strong { color:#f4f7fb;font:600 .94rem Manrope; }.command-alert-value { color:#f4f7fb;font:700 1.25rem Manrope;margin:11px 0 4px; }.command-alert p { color:#9eb0bc;font-size:.78rem;line-height:1.45;margin:0 0 8px; }.command-alert small { color:#c5d2da;font-size:.72rem; }
.forecast-card { min-height:130px;display:flex;flex-direction:column;gap:5px;border:1px solid rgba(38,198,229,.20);background:linear-gradient(150deg,rgba(9,38,48,.96),rgba(5,22,31,.98));padding:15px;border-radius:13px;margin:5px 0 14px; }
.forecast-card span { color:#8da3b4;font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em; }.forecast-card strong { color:#f4f7fb;font:700 1.32rem Manrope;margin-top:5px; }.forecast-card small { color:#9eb0bc;font-size:.7rem; }.forecast-positive { border-top:2px solid #27d17f; }.forecast-risk { border-top:2px solid #ff5b57; }
.recommendation-card { min-height:244px;border:1px solid rgba(217,167,46,.26);background:linear-gradient(145deg,rgba(14,39,45,.97),rgba(5,21,30,.98));padding:17px;border-radius:14px;margin:7px 0 13px; }
.recommendation-head { display:flex;justify-content:space-between;align-items:flex-start;gap:10px;border-bottom:1px solid rgba(141,163,180,.14);padding-bottom:11px;margin-bottom:12px; }.recommendation-head strong { color:#f4f7fb;font:600 1rem Manrope; }.recommendation-head span { flex:0 0 auto;color:#76e8ad;background:rgba(39,209,127,.1);padding:4px 7px;border-radius:6px;font-size:.63rem;font-weight:700; }
.recommendation-grid { display:grid;grid-template-columns:1fr 1fr;gap:11px 18px; }.recommendation-grid small { color:#d9a72e;font-size:.57rem;font-weight:800;letter-spacing:.09em; }.recommendation-grid p { color:#b8c7d0;font-size:.74rem;line-height:1.42;margin:4px 0 0; }
.segment-tile { min-height:108px;border:1px solid rgba(38,198,229,.18);background:linear-gradient(145deg,rgba(9,38,48,.94),rgba(5,23,32,.97));border-radius:14px;padding:15px;margin:5px 0 10px;display:flex;align-items:center;gap:13px; }
.segment-icon { width:42px;height:42px;flex:0 0 42px;display:grid!important;place-items:center;border-radius:12px;background:rgba(38,198,229,.11);color:#53d8ee;font-size:23px; }.segment-tile > div:last-child { display:flex;flex-direction:column;gap:3px; }.segment-tile span { color:#a8bbc6;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em; }.segment-tile strong { color:#f4f7fb;font:700 1.48rem Manrope; }.segment-tile small { color:#78909e;font-size:.65rem; }
.player-identity { display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:20px;border:1px solid rgba(217,167,46,.34);background:radial-gradient(circle at 80% 0,rgba(39,209,127,.08),transparent 32%),linear-gradient(120deg,rgba(13,44,50,.98),rgba(6,23,32,.99));border-radius:18px;padding:23px 25px;margin:10px 0 20px;box-shadow:0 16px 36px rgba(0,0,0,.16); }
.player-avatar { width:70px;height:70px;display:grid!important;place-items:center;border-radius:18px;background:linear-gradient(145deg,rgba(217,167,46,.22),rgba(39,209,127,.14));border:1px solid rgba(217,167,46,.45);color:#e8c15f;font-size:38px;box-shadow:inset 0 0 20px rgba(217,167,46,.08); }.player-identity-main { min-width:0; }.identity-eyebrow { color:#d9a72e;font-size:.64rem;font-weight:800;letter-spacing:.14em; }.player-identity h3 { color:#f4f7fb!important;margin:4px 0 11px;font-size:1.72rem;letter-spacing:.01em; }.identity-attributes { display:flex;flex-wrap:wrap;gap:7px; }.identity-attributes > span { display:inline-flex;align-items:center;gap:5px;color:#b8c8d1;background:rgba(141,163,180,.08);border:1px solid rgba(141,163,180,.13);border-radius:8px;padding:5px 8px;font-size:.72rem; }.identity-attributes i { color:#76a7b6;font-size:15px; }.identity-status { display:flex;flex-direction:column;align-items:flex-end;gap:8px; }.identity-status > strong { display:inline-flex;align-items:center;gap:6px;padding:8px 11px;border-radius:9px;font-size:.72rem;white-space:nowrap; }.identity-status i { font-size:16px; }.identity-status small { color:#8da3b4;font-size:.66rem; }.identity-good { color:#76e8ad;background:rgba(39,209,127,.1);border:1px solid rgba(39,209,127,.28); }.identity-risk { color:#ff8d89;background:rgba(255,91,87,.1);border:1px solid rgba(255,91,87,.28); }
.player-fact { min-height:132px;border:1px solid rgba(141,163,180,.17);background:linear-gradient(145deg,rgba(9,36,46,.95),rgba(5,22,31,.98));border-radius:14px;padding:17px;margin:6px 0 12px;display:flex;align-items:flex-start;gap:13px;box-shadow:0 10px 25px rgba(0,0,0,.09); }
.player-fact-icon { width:43px;height:43px;flex:0 0 43px;display:grid!important;place-items:center;border-radius:12px;background:rgba(217,167,46,.11);border:1px solid rgba(217,167,46,.18);color:#e8c15f;font-size:23px; }.player-fact-copy { min-width:0;display:flex;flex-direction:column;gap:6px; }.player-fact span { color:#9eb0bc;font-size:.69rem;font-weight:700;text-transform:uppercase;letter-spacing:.055em; }.player-fact strong { color:#f4f7fb;font:700 1.27rem Manrope;overflow-wrap:anywhere;line-height:1.18; }.player-fact small { color:#8299a7;font-size:.69rem;line-height:1.35; }
.element-container { max-width:100%; }
button[kind="primary"] {background:linear-gradient(90deg,#0b8056,#16a56f)!important;border:0!important;}
hr {border-color:rgba(141,163,180,.12)!important}
[data-testid="stSidebar"] div[role="radiogroup"] label { padding:.48rem .6rem;border-radius:9px;margin:2px 0; }
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background:linear-gradient(90deg,rgba(217,167,46,.18),rgba(39,209,127,.08));border-left:2px solid #d9a72e; }
@media (min-width: 601px) and (max-width: 900px) {
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) { flex-wrap:wrap!important;gap:.7rem!important; }
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"] { min-width:calc(50% - .4rem)!important;flex:1 1 calc(50% - .4rem)!important;width:calc(50% - .4rem)!important; }
}
@media (max-width: 768px) {
  .block-container { padding: .75rem .7rem 2rem; }
  .page-title { font-size:1.42rem; }
  .page-subtitle { font-size:.82rem; margin-bottom:12px; }
  .live-pill { font-size:.68rem; padding:5px 8px; }
  [data-testid="stMetric"] { min-height:132px; padding:13px; }
  [data-testid="stMetricValue"] { font-size:1.55rem!important; }
  .stPlotlyChart { padding:2px; border-radius:10px; }
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:.65rem; }
  [data-testid="column"] { min-width:100% !important; flex:1 1 100% !important; }
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"] { min-width:calc(50% - .4rem)!important;flex:1 1 calc(50% - .4rem)!important;width:calc(50% - .4rem)!important; }
  [data-testid="stDataFrame"] { overflow-x:auto; }
  [data-testid="stTabs"] [data-baseweb="tab-list"] { overflow-x:auto;scrollbar-width:thin;justify-content:flex-start; }
  [data-testid="stTabs"] [role="tab"] { flex:0 0 auto;white-space:nowrap;padding-left:.75rem;padding-right:.75rem; }
  [data-testid="stDownloadButton"] button { width:100%; }
  .stPlotlyChart > div { min-width:0!important;width:100%!important; }
  .recommendation-grid { grid-template-columns:1fr; }.recommendation-card,.forecast-card,.command-alert { min-height:auto; }
  .player-identity { grid-template-columns:auto 1fr;padding:17px; }.identity-status { grid-column:1/-1;align-items:flex-start; }.player-avatar { width:55px;height:55px;font-size:30px; }.player-identity h3 { font-size:1.4rem; }.player-fact,.segment-tile { min-height:auto; }
  .gambit-brand { padding:12px 10px; margin-bottom:12px; }
  .brand-coin { width:44px;height:44px;font-size:22px; }
  .brand-name { font-size:16px; }
}
@media (max-width: 600px) {
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"] { min-width:100%!important;flex:1 1 100%!important;width:100%!important; }
  [data-testid="stMetric"] { min-height:126px; }
  [data-testid="stMetricLabel"] { min-height:auto;margin-bottom:.35rem; }
  .identity-attributes > span { flex:1 1 auto;justify-content:center; }
  .player-fact { padding:14px; }.player-fact-icon { width:38px;height:38px;flex-basis:38px;font-size:20px; }
}
</style>
"""


LIGHT_CSS = """
<style>
.stApp { background:radial-gradient(circle at 80% -10%,#e8f5f4 0,#f5f7fa 38%,#eef2f6 100%);color:#13232d; }
.stApp [data-testid="stMarkdownContainer"] p,.stApp [data-testid="stMarkdownContainer"] li,.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stWidgetLabel"] p,.stApp label { color:#354d5a; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#ffffff 0%,#edf3f6 100%);border-right:1px solid #d6b761; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,[data-testid="stSidebar"] label { color:#263b47; }
[data-testid="stSidebarNavLink"] span { color:#344c58; }[data-testid="stSidebarNavSeparator"] { color:#647985; }
[data-testid="stSidebarNavLink"][aria-current="page"] { color:#10242d;background:linear-gradient(90deg,rgba(217,167,46,.25),rgba(39,209,127,.12)); }
h1,h2,h3,h4,h5,h6,.page-title,.panel-title { color:#112731!important; }.page-subtitle { color:#526a78; }.eyebrow { color:#a97808; }
[data-testid="stMetric"] { background:linear-gradient(145deg,#ffffff,#edf7f4);border-color:rgba(11,128,86,.22);box-shadow:0 8px 24px rgba(25,48,60,.08); }
[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] p { color:#526a78!important; }[data-testid="stMetricValue"] { color:#112731; }[data-testid="stMetricDelta"] { color:#46606d; }
.filter-summary { background:#eef8fa; }.filter-summary strong { color:#18313c; }.filter-summary span,.filter-summary small { color:#5c7080; }
.insight-card,.app-state { background:linear-gradient(145deg,#ffffff,#f2f6f7);color:#18313c; }.insight-card strong,.app-state strong { color:#18313c; }.insight-card small,.app-state p,.app-state small { color:#5c7080; }
.command-alert,.forecast-card,.recommendation-card { background:linear-gradient(145deg,#ffffff,#f2f6f7);box-shadow:0 8px 22px rgba(25,48,60,.07); }.command-alert-top strong,.command-alert-value,.forecast-card strong,.recommendation-head strong { color:#18313c; }.command-alert p,.command-alert small,.forecast-card span,.forecast-card small,.recommendation-grid p { color:#5c7080; }
.segment-tile,.player-identity,.player-fact { background:linear-gradient(145deg,#ffffff,#eef4f5);box-shadow:0 9px 24px rgba(25,48,60,.07);border-color:#d6e2e6; }.segment-tile span,.segment-tile small,.identity-status small,.player-fact span,.player-fact small { color:#526a78; }.segment-tile strong,.player-identity h3,.player-fact strong { color:#18313c!important; }.segment-icon { background:#e6f6f8;color:#087b91; }.player-avatar { background:linear-gradient(145deg,#fff4d6,#e2f6ee);color:#9a6b00; }.identity-attributes > span { color:#3e5966;background:#f6f9fa;border-color:#dce5e9; }.identity-attributes i { color:#337587; }.player-fact-icon { background:#fff6dc;color:#9a6b00;border-color:#ecdba9; }
.stPlotlyChart { background:linear-gradient(145deg,#ffffff,#f6f9fa);border-color:#dbe4e9; }
[data-baseweb="select"] > div,[data-testid="stDateInput"] input,[data-testid="stTextInput"] input { background:#ffffff!important;color:#18313c!important;border-color:#cad8de!important; }[data-baseweb="select"] span,[data-baseweb="popover"] li { color:#18313c!important; }
[data-testid="stTabs"] [role="tab"] { color:#526a78; }[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color:#087b5a;font-weight:700; }[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background:#0b8056; }
[data-testid="stDownloadButton"] button,.stApp button[kind="secondary"] { background:#ffffff;color:#18313c;border-color:#c8d7dd; }.stApp button[kind="secondary"] p { color:#18313c!important; }
[data-testid="stAlert"] { background:#ffffff;color:#25404d;border-color:#d7e2e7; }[data-testid="stAlert"] p { color:#354d5a!important; }
[data-testid="stProgress"] > div > div { background:#dce8e9; }
div[data-testid="stDataFrame"] { background:#ffffff;border-color:#d2dfe4;box-shadow:0 8px 20px rgba(25,48,60,.05); }
hr { border-color:#d8e2e6!important; }
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
