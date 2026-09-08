from __future__ import annotations

import pandas as pd
import streamlit as st

from database.store import company_repository, sec_filing_repository
from services.ncav import calculate_ncav, calculate_ncav_per_share, calculate_net_cash, calculate_nnwc, calculate_price_to_ncav
from services.sec import (
    format_cik,
    sec_company_service,
    sec_concept_mapper,
    sec_filing_service,
    sec_submissions_service,
    sec_xbrl_service,
)

st.set_page_config(page_title="SEC Fundamental Research — InvestiCore", page_icon="🏛️", layout="wide")

st.title("🏛️ SEC Fundamental Research & Filing Explorer")
st.caption("Primary-source SEC EDGAR filing ingestion, CIK identification, and structured financial extraction")

# --- SECTION 1: COMPANY INTAKE ---
with st.container():
    st.subheader("1. Company Intake & SEC Identification")
    st.markdown("Enter a stock ticker symbol to resolve its canonical SEC CIK, retrieve official submissions, and ingest primary-source filings.")

    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_input = st.text_input(
            "Stock Ticker Symbol",
            placeholder="e.g. META, AAPL, MSFT, INTC, BBBY",
            help="Case-insensitive ticker symbol",
            key="sec_ticker_input",
        )
    with col2:
        st.write("")
        st.write("")
        research_btn = st.button("🔎 Research SEC Filings", type="primary", use_container_width=True)

selected_company = None

if ticker_input.strip():
    clean_ticker = ticker_input.strip().upper()
    sec_record = sec_company_service.get_company_by_ticker(clean_ticker)

    if sec_record:
        cik = sec_record["cik"]
        st.success(f"✅ Resolved SEC CIK: **{cik}** | Entity: **{sec_record['name']}**")

        # Fetch detailed SEC profile
        with st.spinner(f"Loading SEC profile for CIK {cik}..."):
            sec_details = sec_submissions_service.get_company_details(cik)

        # Upsert company in local repository
        existing_comp = company_repository.get_by_ticker(clean_ticker)
        comp_payload = {
            "ticker": clean_ticker,
            "name": sec_record["name"],
            "cik": cik,
            "sic": sec_details.get("sic") if sec_details else None,
            "industry": sec_details.get("sic_description") if sec_details else "N/A",
            "sector": sec_details.get("category") if sec_details else "N/A",
            "website": sec_details.get("website") if sec_details else "",
            "description": f"SEC Registered Entity (CIK: {cik}, State: {sec_details.get('state_of_incorporation', 'N/A') if sec_details else 'N/A'})",
            "status": existing_comp.get("status", "Researching") if existing_comp else "Researching",
        }

        if existing_comp:
            selected_company = company_repository.update(existing_comp["id"], comp_payload)
        else:
            selected_company = company_repository.create(comp_payload)

        # Render Company Profile Cards
        mcol1, mcol2, mcol3, mcol4 = st.columns(4)
        mcol1.metric("Canonical CIK", cik)
        mcol2.metric("SIC Industry", f"{sec_details.get('sic', 'N/A') if sec_details else 'N/A'}")
        mcol3.metric("Fiscal Year End", f"{sec_details.get('fiscal_year_end', 'N/A') if sec_details else 'N/A'}")
        mcol4.metric("State of Inc.", f"{sec_details.get('state_of_incorporation', 'N/A') if sec_details else 'N/A'}")

        if sec_details and sec_details.get("business_address"):
            st.caption(f"📍 Business Address: {sec_details['business_address']}")

    else:
        st.error(f"Could not resolve SEC CIK for ticker '{clean_ticker}'. Please verify the symbol or check SEC EDGAR.")

# --- SECTION 2: SEC FILINGS DISCOVERY & STORAGE ---
if selected_company:
    st.divider()
    st.subheader("2. SEC Filings Archive & Ingestion")

    fcol1, fcol2, fcol3 = st.columns([2, 1, 1])
    with fcol1:
        form_filter = st.multiselect(
            "Filter Form Types",
            options=["10-K", "10-Q", "8-K", "DEF 14A", "4", "20-F", "6-K", "13D", "13G"],
            default=["10-K", "10-Q", "8-K", "DEF 14A"],
        )
    with fcol2:
        filing_limit = st.slider("Filing Limit", min_value=10, max_value=100, value=30, step=10)
    with fcol3:
        st.write("")
        st.write("")
        sync_filings_btn = st.button("📥 Sync & Store Filings", use_container_width=True)

    if sync_filings_btn or research_btn:
        with st.spinner(f"Ingesting latest SEC filings for {selected_company['name']}..."):
            saved = sec_filing_service.sync_company_filings(
                company_id=selected_company["id"],
                cik=selected_company.get("cik") or cik,
                filing_repository=sec_filing_repository,
                form_types=form_filter,
                limit=filing_limit,
            )
            st.toast(f"Synchronized {len(saved)} filings into repository!", icon="📥")

    # Load stored filings for this company
    stored_filings = sec_filing_repository.list_by_company(
        company_id=selected_company["id"],
        form_types=form_filter,
        limit=filing_limit,
    )

    if stored_filings:
        table_rows = []
        for f in stored_filings:
            table_rows.append(
                {
                    "Form": f.get("form_type"),
                    "Filing Date": f.get("filing_date"),
                    "Report Period": f.get("report_date") or "N/A",
                    "Accession Number": f.get("accession_number"),
                    "8-K Items": f.get("items") or "-",
                    "XBRL": "✅ Yes" if f.get("is_xbrl") else "No",
                    "Status": f.get("parsed_status", "Unparsed"),
                    "Primary Document": f.get("primary_document"),
                    "EDGAR URL": f.get("filing_url"),
                }
            )

        df_filings = pd.DataFrame(table_rows)

        st.dataframe(
            df_filings,
            column_config={
                "EDGAR URL": st.column_config.LinkColumn("EDGAR Source", display_text="🔗 View Filing"),
            },
            use_container_width=True,
            hide_index=True,
        )

        # Filing Inspector / Document Viewer
        with st.expander("📄 View Raw SEC Document & Verification Hash", expanded=False):
            acc_list = [f["accession_number"] for f in stored_filings]
            selected_acc = st.selectbox("Select Filing Accession Number to Inspect", acc_list)
            target_f = next((f for f in stored_filings if f["accession_number"] == selected_acc), None)

            if target_f:
                st.markdown(f"**Form:** `{target_f.get('form_type')}` | **Filing Date:** `{target_f.get('filing_date')}` | **Primary Document:** `{target_f.get('primary_document')}`")
                st.markdown(f"**Direct URL:** [{target_f.get('filing_url')}]({target_f.get('filing_url')})")

                fetch_doc_btn = st.button("📥 Retrieve Document Content & Compute SHA256", key="fetch_raw_doc_btn")
                if fetch_doc_btn:
                    with st.spinner("Fetching filing document from SEC..."):
                        content, chash = sec_filing_service.fetch_filing_document(
                            cik=selected_company.get("cik") or cik,
                            accession_number=target_f["accession_number"],
                            primary_document=target_f.get("primary_document", ""),
                        )
                        if content:
                            st.success(f"✅ Document retrieved successfully! SHA256 Hash: `{chash}`")
                            st.text_area("Document Preview (First 5,000 characters)", value=content[:5000], height=300)
                        else:
                            st.warning("Could not download raw document content from SEC EDGAR.")

    else:
        st.info("No filings stored for this company yet. Click '📥 Sync & Store Filings' to import from SEC EDGAR.")

    # --- SECTION 3: XBRL EXTRACTION & NCAV PREVIEW ---
    st.divider()
    st.subheader("3. Structured XBRL Extraction & Net-Net / NCAV Preview")

    with st.spinner("Analyzing SEC XBRL Company Facts..."):
        facts = sec_xbrl_service.get_company_facts(selected_company.get("cik") or cik)

    if facts:
        st.success(f"✅ XBRL facts archive located for CIK {selected_company.get('cik') or cik}!")

        # Extract Canonical Metrics
        cash_m = sec_concept_mapper.map_metric_from_facts(facts, "cash")
        curr_assets_m = sec_concept_mapper.map_metric_from_facts(facts, "total_current_assets")
        curr_liab_m = sec_concept_mapper.map_metric_from_facts(facts, "current_liabilities")
        tot_liab_m = sec_concept_mapper.map_metric_from_facts(facts, "total_liabilities")
        shares_m = sec_concept_mapper.map_metric_from_facts(facts, "shares_diluted")
        rec_m = sec_concept_mapper.map_metric_from_facts(facts, "accounts_receivable")
        inv_m = sec_concept_mapper.map_metric_from_facts(facts, "inventory")

        # Convert raw dollars to Millions ($M)
        cash_val = (cash_m["value"] / 1_000_000.0) if cash_m and cash_m.get("value") is not None else None
        curr_assets_val = (curr_assets_m["value"] / 1_000_000.0) if curr_assets_m and curr_assets_m.get("value") is not None else None
        curr_liab_val = (curr_liab_m["value"] / 1_000_000.0) if curr_liab_m and curr_liab_m.get("value") is not None else None
        tot_liab_val = (tot_liab_m["value"] / 1_000_000.0) if tot_liab_m and tot_liab_m.get("value") is not None else None
        shares_val = (shares_m["value"] / 1_000_000.0) if shares_m and shares_m.get("value") is not None else 1.0
        rec_val = (rec_m["value"] / 1_000_000.0) if rec_m and rec_m.get("value") is not None else 0.0
        inv_val = (inv_m["value"] / 1_000_000.0) if inv_m and inv_m.get("value") is not None else 0.0

        # Calculations
        ncav = calculate_ncav(curr_assets_val, tot_liab_val)
        ncav_ps = calculate_ncav_per_share(ncav, shares_val)
        nnwc = calculate_nnwc(
            cash=cash_val,
            marketable_securities=0.0,
            accounts_receivable=rec_val,
            inventory=inv_val,
            other_current_assets=0.0,
            total_liabilities=tot_liab_val,
        )
        nnwc_ps = calculate_ncav_per_share(nnwc, shares_val)

        # Metric Overview Columns
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Assets ($M)", f"${curr_assets_val:,.1f}M" if curr_assets_val is not None else "N/A")
        c2.metric("Total Liabilities ($M)", f"${tot_liab_val:,.1f}M" if tot_liab_val is not None else "N/A")
        c3.metric("NCAV ($M)", f"${ncav:,.1f}M" if ncav is not None else "N/A")
        c4.metric("NCAV / Share", f"${ncav_ps:,.2f}" if ncav_ps is not None else "N/A")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Cash & Equiv ($M)", f"${cash_val:,.1f}M" if cash_val is not None else "N/A")
        c6.metric("Receivables ($M)", f"${rec_val:,.1f}M" if rec_val is not None else "N/A")
        c7.metric("NNWC ($M)", f"${nnwc:,.1f}M" if nnwc is not None else "N/A")
        c8.metric("NNWC / Share", f"${nnwc_ps:,.2f}" if nnwc_ps is not None else "N/A")

        # Provenance & Audit Table
        st.markdown("#### 🔍 Primary-Source Provenance & Audit Trail")
        prov_rows = []
        for m_obj in [cash_m, curr_assets_m, tot_liab_m, rec_m, inv_m, shares_m]:
            if m_obj:
                prov_rows.append(
                    {
                        "Metric": m_obj["metric_name"],
                        "Reported Value": f"{m_obj['value']:,} {m_obj.get('unit', '')}",
                        "XBRL Concept": m_obj["source_concept"],
                        "Form": m_obj.get("form"),
                        "Filing Date": m_obj.get("filing_date"),
                        "Period End": m_obj.get("period_end"),
                        "Confidence": m_obj["confidence"],
                        "Accession": m_obj.get("accession_number"),
                    }
                )
        if prov_rows:
            st.dataframe(pd.DataFrame(prov_rows), use_container_width=True, hide_index=True)

    else:
        st.info("No XBRL company facts dataset found for this entity.")
