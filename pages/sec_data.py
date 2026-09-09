from __future__ import annotations

import pandas as pd
import streamlit as st

from database.client import get_supabase_client
from services.sec.company import sec_company_service
from services.sec.filings import sec_filing_service
from services.sec.phase1_ingestion import Phase1SECIngestionService
from services.sec.submissions import sec_submissions_service

st.title("SEC financial history")
st.caption("Storage-backed, accession-idempotent filing ingestion and normalized financial history.")

client = get_supabase_client()
if client is None:
    st.error("Configure SUPABASE_URL and SUPABASE_KEY before using the SEC data workspace.")
    st.stop()

with st.form("company_lookup"):
    ticker = st.text_input("Ticker", placeholder="AAPL")
    download_html = st.checkbox(
        "Archive primary SEC HTML filings in the background",
        value=False,
        help="The financial refresh returns immediately. A background worker archives missing primary filing HTML in Supabase Storage.",
    )
    refresh = st.form_submit_button("Refresh SEC data", type="primary", icon=":material/refresh:")

if not ticker.strip():
    st.info("Enter a US-listed ticker to begin an initial SEC load or a later incremental refresh.")
    st.stop()

profile = sec_company_service.get_company_by_ticker(ticker)
if profile is None:
    st.error("The SEC ticker directory did not return a matching company.")
    st.stop()

companies = client.schema("investicorev2").table("companies")
company_result = companies.upsert(
    {"ticker": profile["ticker"], "cik": profile["cik"], "legal_name": profile["name"]},
    on_conflict="cik",
).execute()
company = company_result.data[0]

st.subheader(f"{company['legal_name']} ({company['ticker']})")
st.caption(f"CIK {company['cik']}")

if refresh:
    service = Phase1SECIngestionService(sec_submissions_service, sec_filing_service, client)
    with st.status("Refreshing SEC data", expanded=True) as status:
        st.write("Discovering required filings and comparing accession numbers.")
        try:
            outcome = service.refresh_company_sec_data(
                company["id"], company["cik"]
            )
            st.write(
                f"Discovered {outcome['discovered_count']} filings; persisted {outcome['raw_facts_saved']} new raw facts; "
                f"processed {outcome['normalized_count']} financial records."
            )
            if download_html:
                started = service.start_primary_html_download(company["id"], company["cik"])
                if started:
                    st.toast("Primary SEC HTML archival started in the background.", icon=":material/download:")
                else:
                    st.info("Primary SEC HTML archival is already running for this company.")
            status.update(label=f"Refresh {outcome['status'].lower().replace('_', ' ')}", state="complete")
        except Exception as exc:
            status.update(label="Refresh failed", state="error")
            st.exception(exc)

if st.button("Archive companion artifacts", icon=":material/folder_zip:"):
    service = Phase1SECIngestionService(sec_submissions_service, sec_filing_service, client)
    with st.status("Archiving exhibits and XBRL artifacts", expanded=True) as status:
        outcome = service.archive_companion_artifacts(company["id"], company["cik"])
        status.update(label=f"Archived {outcome['archived']} artifacts; {outcome['failed']} filings deferred", state="complete")

filings_result = (
    client.schema("investicorev2").table("sec_filings").select("id,form_type,filing_date,report_date,accession_number,ingestion_status,is_amendment,is_preferred,amends_filing_id,superseded_by_filing_id,sec_url")
    .eq("company_id", company["id"]).order("filing_date", desc=True).execute()
)
filings = filings_result.data or []

metrics = {
    "10-K stored": sum(row["form_type"].startswith("10-K") for row in filings),
    "10-Q stored": sum(row["form_type"].startswith("10-Q") for row in filings),
    "8-K stored": sum(row["form_type"].startswith("8-K") for row in filings),
    "Last refresh": "Not run",
}
refreshes = client.schema("investicorev2").table("sec_refresh_runs").select("completed_at,status").eq("company_id", company["id"]).order("started_at", desc=True).limit(1).execute().data or []
if refreshes:
    metrics["Last refresh"] = refreshes[0]["completed_at"] or refreshes[0]["status"]

for column, (label, value) in zip(st.columns(4), metrics.items()):
    column.metric(label, value)

st.subheader("Filing archive")
if filings:
    for filing in filings:
        if filing["is_amendment"]:
            filing["relationship"] = "Preferred amendment" if filing["is_preferred"] else "Amendment"
        elif filing["superseded_by_filing_id"]:
            filing["relationship"] = "Superseded by amendment"
        else:
            filing["relationship"] = "Preferred" if filing["is_preferred"] else "Historical"
    st.dataframe(
        pd.DataFrame(filings),
        column_config={"sec_url": st.column_config.LinkColumn("SEC filing"), "id": None, "amends_filing_id": None, "superseded_by_filing_id": None},
        hide_index=True,
    )
else:
    st.info("No filings are stored yet. Run the refresh to begin the initial load.")

validation_rows = (
    client.schema("investicorev2").table("financial_validation_issues")
    .select("check_name,validation_status,severity,message,created_at")
    .eq("company_id", company["id"]).order("created_at", desc=True).limit(30).execute().data
    or []
)
if validation_rows:
    with st.expander("Data-quality checks"):
        st.dataframe(pd.DataFrame(validation_rows), hide_index=True)

service = Phase1SECIngestionService(sec_submissions_service, sec_filing_service, client)
annual_history = service.financial_history(company["id"], "Annual")
quarterly_history = service.financial_history(company["id"], "Quarterly")
ttm = service.current_ttm(company["id"])

st.subheader("Financial history")
display_col, percentage_col = st.columns(2)
with display_col:
    display_unit = st.selectbox("Amount unit", ["Millions", "Billions"], index=0)
with percentage_col:
    show_yoy = st.checkbox("Show year-over-year change", value=False)

unit_divisor = 1_000_000 if display_unit == "Millions" else 1_000_000_000
unit_label = "$M" if display_unit == "Millions" else "$B"
per_share_metrics = {"eps_basic", "eps_diluted"}
period_metadata = {"id", "fiscal_year", "fiscal_period", "period_end", "source_filing_id"}


def financial_display(records: list[dict], period_type: str) -> pd.DataFrame:
    rows = [{key: value for key, value in row.items() if key != "metrics"} | row["metrics"] for row in records]
    frame = pd.DataFrame(rows)
    metric_columns = [column for column in frame.columns if column not in period_metadata]
    original_values = frame[metric_columns].apply(pd.to_numeric, errors="coerce")

    for column in metric_columns:
        if column not in per_share_metrics:
            frame[column] = original_values[column] / unit_divisor
        else:
            frame[column] = original_values[column]

    if show_yoy:
        comparison_periods = 1 if period_type == "Annual" else 4
        for column in metric_columns:
            frame[f"{column} YoY %"] = (original_values[column].pct_change(comparison_periods) * 100).round(2)
    return frame


annual_tab, quarterly_tab, ttm_tab = st.tabs(["Annual", "Quarterly", "TTM"])
with annual_tab:
    if annual_history:
        st.dataframe(
            financial_display(annual_history, "Annual"),
            hide_index=True,
        )
        st.caption(f"Amounts shown in {unit_label}; EPS remains per share.")
    else:
        st.info("Annual financial observations appear here after a 10-K is normalized.")
with quarterly_tab:
    if quarterly_history:
        st.dataframe(
            financial_display(quarterly_history, "Quarterly"),
            hide_index=True,
        )
        st.caption(f"Amounts shown in {unit_label}; quarterly YoY compares the same fiscal quarter one year earlier.")
    else:
        st.info("Quarterly financial observations appear here after a 10-Q is normalized.")
with ttm_tab:
    if ttm:
        ttm_display = {}
        for key, value in ttm.items():
            if key == "period_label" or value is None:
                ttm_display[key.replace("_", " ").title()] = value
            elif key in per_share_metrics:
                ttm_display[key.replace("_", " ").title()] = value
            else:
                ttm_display[key.replace("_", " ").title()] = float(value) / unit_divisor
        st.table(ttm_display)
        st.caption(f"TTM amounts shown in {unit_label}; EPS remains per share.")
    else:
        st.info("TTM becomes available after four quarterly observations are normalized. Annual values are never substituted.")

with st.expander("Financial provenance"):
    provenance = (
        client.schema("investicorev2").table("financial_metrics")
        .select("metric_name,metric_value,source_accession_number,xbrl_namespace,xbrl_tag,calculation_method,confidence,is_derived")
        .eq("company_id", company["id"]).eq("is_preferred", True).limit(100).execute().data
        or []
    )
    if provenance:
        st.dataframe(pd.DataFrame(provenance), hide_index=True)
    else:
        st.info("Provenance appears after financial facts are normalized.")