from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from data.importer import (
    CONTRACTS, activate_import, cross_validate, file_fingerprint, import_history,
    infer_dataset, issues_frame, quality_summary, read_upload, suggest_mapping, validate_frame,
)
from data.repository import get_repository
from ui.components import data_table
from ui.theme import page_header


def _quality_cards(summary: dict) -> None:
    items = [("Rows inspected",f"{summary['rows']:,}","table_rows"),("Datasets",str(summary['datasets']),"dataset"),("Quality score",f"{summary['score']}/100","verified"),("Blocking errors",str(summary['errors']),"error"),("Warnings",str(summary['warnings']),"warning")]
    columns=st.columns(5)
    for column,(label,value,icon) in zip(columns,items):
        with column: st.markdown(f"<div class='import-kpi'><span class='material-symbols-rounded'>{icon}</span><small>{label}</small><strong>{value}</strong></div>",unsafe_allow_html=True)


def _mapping_editor(file_index: int, fingerprint: str, filename: str, frame: pd.DataFrame, dataset: str) -> dict[str,str|None]:
    contract=CONTRACTS[dataset]; suggested=suggest_mapping(dataset,frame.columns); mapping={}
    st.markdown(f"##### {filename} → {contract.label}")
    st.caption(f"{len(frame):,} rows · {len(frame.columns):,} source columns · primary key: {contract.primary_key}")
    cols=st.columns(3)
    options=["— Not mapped —",*frame.columns.tolist()]
    for index,(field,spec) in enumerate(contract.fields.items()):
        default=suggested[field]; default_index=options.index(default) if default in options else 0
        with cols[index%3]:
            value=st.selectbox(f"{field}{' *' if spec.required else ''}",options,index=default_index,key=f"map_{file_index}_{fingerprint}_{field}",help=f"Expected type: {spec.kind}")
            mapping[field]=None if value==options[0] else value
    return mapping


def _future_connectors() -> None:
    st.markdown("### Connector roadmap")
    st.caption("CSV and Excel are the active pilot connectors. The following adapters share the same contract and quality engine but remain intentionally disabled until credentials, tenancy and scheduling are production-ready.")
    cols=st.columns(4)
    items=[("PostgreSQL / MySQL","database","Schema discovery + incremental watermark","Prepared"),("Amazon S3","cloud","Object events + partition discovery","Prepared"),("REST API","api","Pagination + retry + rate limiting","Planned"),("Daily pipelines","schedule","Run history + alerts + idempotency","Prepared")]
    for col,(name,icon,body,status) in zip(cols,items):
        with col: st.markdown(f"<div class='connector-card'><header><span class='material-symbols-rounded'>{icon}</span><b>{status}</b></header><strong>{name}</strong><p>{body}</p></div>",unsafe_allow_html=True)


def render(ctx) -> None:
    page_header("DATA IMPORT STUDIO","Map, validate and activate client CSV data safely","Data Operations")
    st.markdown("<section class='import-hero'><span class='material-symbols-rounded'>upload_file</span><div><small>CSV &amp; EXCEL PILOT CONNECTOR</small><h2>From client files to governed intelligence</h2><p>Nothing reaches a dashboard until schemas, types, keys and relationships pass validation.</p></div></section>",unsafe_allow_html=True)
    upload_tab, quality_tab, history_tab, roadmap_tab=st.tabs(["1 · Upload & map","2 · Quality report","3 · Run history","Connector roadmap"])
    with upload_tab:
        st.info("Upload UTF-8 CSV or Excel (.xlsx) files up to 50 MB each. One workbook with named sheets (players, casino_sessions, ...) or one file per table both work. Required pilot domains: players plus at least one activity file.",icon=":material/info:")
        files=st.file_uploader("Client CSV or Excel files",type=["csv","xlsx","xls"],accept_multiple_files=True,key="csv_import_files")
        parsed=[]; index=0
        for uploaded in files or []:
            try:
                payload=uploaded.getvalue(); sheets=read_upload(uploaded.name,payload)
            except ValueError as exc:
                st.error(str(exc)); continue
            for label,frame in sheets.items():
                detected=infer_dataset(label,frame.columns)
                dataset=st.selectbox(f"Dataset for {label}",list(CONTRACTS),index=list(CONTRACTS).index(detected),format_func=lambda name:CONTRACTS[name].label,key=f"dataset_{index}_{file_fingerprint(payload)}_{label}")
                with st.expander(f"Map {label} · detected as {CONTRACTS[dataset].label}",expanded=True):
                    mapping=_mapping_editor(index,f"{file_fingerprint(payload)}_{label}",label,frame,dataset)
                    st.dataframe(frame.head(5),width="stretch",hide_index=True)
                parsed.append((label,dataset,frame,mapping)); index+=1
        if st.button("Validate all files",type="primary",width="stretch",disabled=not parsed,icon=":material/fact_check:"):
            frames={}; issues=[]
            for filename,dataset,frame,mapping in parsed:
                mapped,file_issues=validate_frame(dataset,frame,mapping); issues.extend(file_issues)
                frames[dataset]=pd.concat([frames.get(dataset,pd.DataFrame()),mapped],ignore_index=True)
            for dataset,frame in frames.items():
                key=CONTRACTS[dataset].primary_key
                duplicate_count=int(frame[key].dropna().duplicated().sum())
                if duplicate_count:
                    from data.importer import QualityIssue
                    issues.append(QualityIssue("ERROR",dataset,key,None,"CROSS_FILE_DUPLICATE",f"{duplicate_count:,} duplicate keys exist across uploaded files."))
            issues.extend(cross_validate(frames)); summary=quality_summary(frames,issues)
            st.session_state["csv_validation"]={"frames":frames,"issues":issues,"summary":summary,"filenames":[item[0] for item in parsed]}
            st.success("Validation completed. Open the Quality report tab.") if summary["ready"] else st.error("Validation completed with blocking errors. Open the Quality report tab.")

    with quality_tab:
        result=st.session_state.get("csv_validation")
        if not result: st.info("Upload, map and validate files to generate a quality report.")
        else:
            summary=result["summary"]; _quality_cards(summary)
            issues=issues_frame(result["issues"])
            if issues.empty: st.success("All blocking controls passed. The dataset is ready for atomic activation.")
            else:
                severity=st.segmented_control("Issue severity",["All","ERROR","WARNING"],default="All",key="quality_severity")
                view=issues if severity=="All" else issues[issues.severity.eq(severity)]
                data_table(view)
                st.download_button("Download quality report",issues.to_csv(index=False),"casino_ai_quality_report.csv","text/csv",icon=":material/download:",width="stretch")
            st.markdown("#### Dataset coverage")
            coverage=pd.DataFrame([{"Dataset":CONTRACTS[name].label,"Rows":len(frame),"Columns":len(frame.columns)} for name,frame in result["frames"].items()])
            data_table(coverage)
            st.warning("Activation replaces the active pilot warehouse atomically. The packaged synthetic demo remains untouched and the previous pilot database is archived.")
            if st.button("Activate validated pilot data",type="primary",width="stretch",disabled=not summary["ready"],icon=":material/published_with_changes:"):
                try:
                    run_id,path=activate_import(result["frames"],result["issues"],result["filenames"])
                    get_repository.clear(); st.session_state.pop("global_date_range",None); st.session_state.pop("global_market",None); st.session_state.pop("csv_validation",None)
                    st.success(f"Import {run_id} activated successfully."); st.rerun()
                except Exception as exc: st.error(f"Activation failed safely; the current warehouse was preserved. {exc}")

    with history_tab:
        history=import_history()
        if history.empty: st.info("No import run has been activated yet.")
        else: data_table(history)
        st.caption("Every activation records status, row count, quality score, errors and warnings. Failed candidates never replace the active warehouse.")
    with roadmap_tab: _future_connectors()
