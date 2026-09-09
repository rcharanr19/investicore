from __future__ import annotations

import pandas as pd
import streamlit as st

from components.historical_matrix import METRIC_GROUPS, build_historical_matrix, format_metric_value
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
all_periods = client.schema("investicorev2").table("financial_periods").select("id,period_type,fiscal_year,fiscal_period,period_end,source_filing_id").eq("company_id", company["id"]).in_("period_type", ["TTM", "Annual", "Quarterly"]).order("period_end", desc=True).execute().data or []
annual_periods = [period for period in all_periods if period["period_type"] == "Annual"]
if not annual_periods:
    st.info("No normalized TTM or annual periods are available yet.")
    st.stop()

range_option = st.selectbox("Historical range", ["5 fiscal years", "10 fiscal years", "All available years"], index=0)
range_limit = {"5 fiscal years": 5, "10 fiscal years": 10, "All available years": len(annual_periods)}[range_option]
historical_periods = list(reversed(annual_periods[:range_limit]))
show_yoy_change = st.checkbox("Show year-over-year change for each metric", value=True)
if st.button("Update Yahoo price and calculate all metrics", type="primary", icon=":material/calculate:"):
    price = fetch_current_price(company["ticker"])
    if price is None:
        st.warning("Yahoo Finance did not return a current price. SEC-only metrics can still be calculated without market ratios.")
        market_price = None
    else:
        market_price = DerivedMetricsService(client).save_latest_market_price(company["id"], company["ticker"], price)
    saved = DerivedMetricsService(client).calculate_all(company["id"], market_price)
    st.success(f"Calculated {saved} metrics across annual, quarterly, and TTM periods.")

period_ids = [period["id"] for period in historical_periods]
normalized = client.schema("investicorev2").table("financial_metrics").select("financial_period_id,metric_name,metric_value").in_("financial_period_id", period_ids).eq("is_preferred", True).execute().data or []
derived = client.schema("investicorev2").table("derived_metrics").select("financial_period_id,metric_name,metric_value,calculated_at").eq("company_id", company["id"]).in_("financial_period_id", period_ids).order("calculated_at", desc=True).execute().data or []
values_by_period: dict[str, dict[str, float | None]] = {period_id: {} for period_id in period_ids}
for metric in normalized:
    values_by_period[metric["financial_period_id"]][metric["metric_name"]] = metric["metric_value"]
for metric in derived:
    values_by_period[metric["financial_period_id"]].setdefault(metric["metric_name"], metric["metric_value"])

ttm_period = next((period for period in all_periods if period["period_type"] == "TTM"), None)
latest_balance_period = next((period for period in all_periods if period["period_type"] == "Quarterly"), annual_periods[0])
snapshot_period_ids = [period["id"] for period in [ttm_period, latest_balance_period] if period]
snapshot_rows = client.schema("investicorev2").table("derived_metrics").select("financial_period_id,metric_name,metric_value,unit").eq("company_id", company["id"]).in_("financial_period_id", snapshot_period_ids).order("calculated_at", desc=True).execute().data or []
snapshot_values: dict[str, dict[str, object]] = {}
for row in snapshot_rows:
    snapshot_values.setdefault(row["metric_name"], row)

st.subheader("Current / TTM snapshot")
snapshot_metrics = [("Revenue", "revenue"), ("EBIT", "ebit"), ("Free cash flow", "free_cash_flow"), ("Cash", "cash"), ("Total debt", "total_debt"), ("Net debt", "net_debt"), ("Operating margin", "operating_margin"), ("ROIC", "roic"), ("P / FCF", "price_to_fcf")]
for start in range(0, len(snapshot_metrics), 3):
    for column, (label, metric_name) in zip(st.columns(3), snapshot_metrics[start:start + 3]):
        item = snapshot_values.get(metric_name)
        value = format_metric_value(item["metric_value"], item["unit"]) if item and item["metric_value"] is not None else "-"
        column.metric(label, value)

st.subheader(f"Historical fundamentals: {range_option}")
default_open = {"Income statement", "Cash flow", "Balance sheet", "Growth & margins", "Profitability & returns", "Financial strength", "Valuation"}
for section in METRIC_GROUPS:
    with st.expander(section, expanded=section in default_open):
        st.dataframe(
            build_historical_matrix(
                historical_periods,
                values_by_period,
                section,
                include_yoy_change=show_yoy_change,
            ),
            hide_index=True,
        )

with st.expander("Data & provenance"):
    audit_period = st.selectbox("Inspect fiscal period", historical_periods, format_func=lambda row: f"FY{row['fiscal_year']} ending {row['period_end']}")
    audit_rows = client.schema("investicorev2").table("financial_metrics").select("metric_name,metric_value,unit,source_accession_number,xbrl_namespace,xbrl_tag,calculation_method,confidence,is_derived,source_period_end").eq("financial_period_id", audit_period["id"]).eq("is_preferred", True).order("metric_name").execute().data or []
    st.dataframe(pd.DataFrame(audit_rows), hide_index=True)

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