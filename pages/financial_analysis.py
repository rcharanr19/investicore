from __future__ import annotations

import pandas as pd
import streamlit as st

from database.client import get_supabase_client
from services.derived_metrics import DerivedMetricsService
from services.financial_fetcher import fetch_current_price
from services.sec.activity import SECActivityService
from services.sec.filings import sec_filing_service
from services.sec.submissions import sec_submissions_service

st.title("Financial analysis")
st.caption("Phase 2 derived metrics based on normalized SEC financials and timestamped market prices.")

client = get_supabase_client()
if client is None:
    st.error("Configure SUPABASE_URL and SUPABASE_KEY before using financial analysis.")
    st.stop()

companies = client.schema("investicorev2").table("companies").select("id,ticker,cik,legal_name").order("ticker").execute().data or []
if not companies:
    st.info("Add and refresh a company on the SEC data page before using financial analysis.")
    st.stop()

company = st.selectbox("Company", companies, format_func=lambda row: f"{row['ticker']} - {row.get('legal_name') or row['ticker']}")
periods = client.schema("investicorev2").table("financial_periods").select("id,period_type,fiscal_year,fiscal_period,period_end").eq("company_id", company["id"]).in_("period_type", ["TTM", "Annual"]).order("period_end", desc=True).execute().data or []
if not periods:
    st.info("No normalized TTM or annual periods are available yet.")
    st.stop()

period = st.selectbox("Financial period", periods, format_func=lambda row: f"{row['period_type']} through {row['period_end']}")
if st.button("Update Yahoo price and calculate metrics", type="primary", icon=":material/calculate:"):
    price = fetch_current_price(company["ticker"])
    if price is None:
        st.warning("Yahoo Finance did not return a current price. SEC-only metrics can still be calculated without market ratios.")
        market_price = None
    else:
        market_price = DerivedMetricsService(client).save_latest_market_price(company["id"], company["ticker"], price)
    rows = DerivedMetricsService(client).calculate_and_save(company["id"], period["id"], market_price)
    st.success(f"Calculated {len(rows)} Phase 2 metrics.")

metrics = client.schema("investicorev2").table("derived_metrics").select("metric_name,metric_value,unit,status,calculation_method,calculated_at").eq("company_id", company["id"]).eq("financial_period_id", period["id"]).order("metric_name").execute().data or []
if metrics:
    frame = pd.DataFrame(metrics)
    percentage_rows = frame["unit"] == "percentage"
    frame.loc[percentage_rows, "metric_value"] = frame.loc[percentage_rows, "metric_value"].astype(float) * 100
    st.dataframe(frame, hide_index=True)
else:
    st.info("Calculate metrics to populate this analysis period.")

st.subheader("SEC activity evidence")
if st.button("Ingest Form 4 and 13D/13G activity", icon=":material/download:"):
    with st.status("Ingesting SEC ownership activity", expanded=True) as status:
        outcome = SECActivityService(client, sec_submissions_service, sec_filing_service).ingest(company["id"], company["cik"])
        status.update(label=f"Stored {outcome['insider_transactions']} Form 4 transactions and {outcome['ownership_disclosures']} ownership disclosures", state="complete")
activity_tab, ownership_tab = st.tabs(["Insider and management Form 4", "Activist and ownership 13D/13G"])
with activity_tab:
    rows = client.schema("investicorev2").table("insider_transactions").select("reporting_person,officer_title,transaction_date,transaction_code,transaction_type,shares_transacted,price_per_share,total_value").eq("company_id", company["id"]).order("transaction_date", desc=True).execute().data or []
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True)
    else:
        st.info("Form 4 activity appears after Form 4 XML ingestion is implemented for this company.")
with ownership_tab:
    rows = client.schema("investicorev2").table("ownership_disclosures").select("holder_name,form_type,filing_date,shares_beneficially_owned,ownership_pct,is_activist,activity_type").eq("company_id", company["id"]).order("filing_date", desc=True).execute().data or []
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True)
    else:
        st.info("13D/13G disclosures report ownership changes. They are not labeled as buys or sells unless an actual transaction is disclosed.")