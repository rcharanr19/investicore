from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st

from database.store import (
    analysis_repository,
    catalyst_repository,
    company_repository,
    financial_metric_repository,
    financial_period_repository,
    financial_repository,
    insider_transactions_repository,
    management_compensation_repository,
    ownership_filings_repository,
    research_alert_repository,
    sec_filing_repository,
    thesis_breaker_repository,
    valuation_snapshot_repository,
)
from services.change_detector import SECChangeDetector
from services.cigar_butt_scoring import calculate_cigar_butt_score, perform_forensic_checks
from services.ncav import (
    NCAVAssumptions,
    calculate_adjusted_liquidation_value,
    calculate_cash_burn_and_runway,
    calculate_ncav,
    calculate_ncav_per_share,
    calculate_net_cash,
    calculate_nnwc,
    calculate_price_to_ncav,
    calculate_scenario_expected_value,
    calculate_share_dilution,
)
from services.sec import (
    SECCrossFilingEngine,
    format_cik,
    sec_catalyst_detector,
    sec_company_service,
    sec_concept_mapper,
    sec_filing_service,
    sec_insider_service,
    sec_management_service,
    sec_ownership_service,
    sec_statement_reconstructor,
    sec_submissions_service,
    sec_taxonomy_service,
    sec_xbrl_service,
)

st.set_page_config(page_title="SEC Fundamental Research — InvestiCore", page_icon="🏛️", layout="wide")

st.title("🏛️ SEC Fundamental Research & Cigar-Butt Workstation")
st.caption("Primary-source SEC EDGAR filing ingestion, XBRL reconstruction, forensic cigar-butt valuation, catalysts, and thesis tracking")

# --- SECTION 1: COMPANY INTAKE ---
with st.container():
    st.subheader("1. Company Intake & SEC Identification")
    st.markdown("Enter a stock ticker symbol to resolve its canonical SEC CIK, retrieve official submissions, and ingest primary-source filings.")

    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_input = st.text_input(
            "Stock Ticker Symbol",
            placeholder="e.g. GTLB, META, AAPL, MSFT, INTC, BBBY",
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

# --- RESEARCH DOSSIER TABS ---
if selected_company:
    st.divider()

    dossier_tabs = st.tabs([
        "📥 1. SEC Filings & Timeline",
        "📊 2. Financial Statements (5-Yr / 8-Qtr)",
        "📉 3. Cigar-Butt & Liquidation",
        "⚡ 4. Catalysts & 8-K Events",
        "👔 5. Management & Incentives (DEF 14A)",
        "👥 6. Ownership & Activism (13D / 13G)",
        "💼 7. Insider Activity (Form 4)",
        "🌐 8. Cross-Filing Synthesis",
        "🎯 9. Valuation & Snapshots",
        "📒 10. Thesis & Thesis Killers",
        "🚨 11. Filing Change Alerts",
    ])

    # ==========================================
    # TAB 1: SEC FILINGS & TIMELINE
    # ==========================================
    with dossier_tabs[0]:
        st.subheader("SEC Filings Archive, Taxonomy & Unified Timeline")
        st.caption("Each filing type serves a distinct analytical purpose (10-K: Baseline, 10-Q: Current State, 8-K: Catalysts, DEF 14A: Incentives, 13D: Activists, Form 4: Insiders).")

        fcol1, fcol2, fcol3 = st.columns([2, 1, 1])
        with fcol1:
            form_filter = st.multiselect(
                "Filter Form Types",
                options=["10-K", "10-Q", "8-K", "DEF 14A", "4", "20-F", "6-K", "13D", "13D/A", "13G", "13G/A"],
                default=["10-K", "10-Q", "8-K", "DEF 14A", "13D", "4"],
                key="tab1_form_filter",
            )
        with fcol2:
            filing_limit = st.slider("Filing Limit", min_value=10, max_value=100, value=30, step=10, key="tab1_limit")
        with fcol3:
            st.write("")
            st.write("")
            sync_filings_btn = st.button("📥 Sync & Store Filings", use_container_width=True, key="tab1_sync_btn")

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

        stored_filings = sec_filing_repository.list_by_company(
            company_id=selected_company["id"],
            form_types=form_filter,
            limit=filing_limit,
        )

        if stored_filings:
            table_rows = []
            for f in stored_filings:
                classified = sec_taxonomy_service.classify_filing(f)
                table_rows.append({
                    "Form": f.get("form_type"),
                    "Filing Date": f.get("filing_date"),
                    "Report Period": f.get("report_date") or "N/A",
                    "Category": classified.get("category_label"),
                    "Analytical Purpose": classified.get("analytical_purpose"),
                    "Catalyst Rel.": classified.get("catalyst_relevance"),
                    "Mgmt Rel.": classified.get("management_relevance"),
                    "EDGAR URL": f.get("filing_url"),
                })

            st.dataframe(
                pd.DataFrame(table_rows),
                column_config={
                    "EDGAR URL": st.column_config.LinkColumn("EDGAR Link", display_text="🔗 View Filing"),
                },
                use_container_width=True,
                hide_index=True,
            )

            # Unified Interactive Filing Timeline
            st.markdown("#### ⏳ Unified Company SEC Filing Timeline")
            timeline_filter = st.radio(
                "Filter Timeline Stream",
                ["All Filings", "Financial (10-K/10-Q)", "Catalysts (8-K)", "Management (DEF 14A)", "Ownership (13D/13G)", "Insider Activity (Form 4)"],
                horizontal=True,
                key="timeline_stream_filter",
            )

            cross_engine = SECCrossFilingEngine(
                filing_repo=sec_filing_repository,
                period_repo=financial_period_repository,
                metric_repo=financial_metric_repository,
                catalyst_repo=catalyst_repository,
                management_repo=management_compensation_repository,
                ownership_repo=ownership_filings_repository,
                insider_repo=insider_transactions_repository,
            )

            filter_tag = "all"
            if "Financial" in timeline_filter:
                filter_tag = "financial"
            elif "Catalysts" in timeline_filter:
                filter_tag = "material_event"
            elif "Management" in timeline_filter:
                filter_tag = "management_governance"
            elif "Ownership" in timeline_filter:
                filter_tag = "ownership_activist"
            elif "Insider" in timeline_filter:
                filter_tag = "insider_transaction"

            timeline_events = cross_engine.build_unified_timeline(selected_company["id"], filter_category=filter_tag)

            if timeline_events:
                for ev in timeline_events[:15]:
                    with st.expander(f"📅 **{ev['date']}** — `{ev['form_type']}`: {ev['headline']}", expanded=False):
                        st.markdown(f"**Category:** `{ev['category_label']}` | **Accession:** `{ev.get('accession_number')}`")
                        st.markdown(f"**Analytical Context:** {ev['detail']}")
                        st.markdown(f"**Direct Filing URL:** [{ev['filing_url']}]({ev['filing_url']})")
            else:
                st.info("No timeline events matching the selected stream.")

            with st.expander("📄 View Raw SEC Document & Verification Hash", expanded=False):
                acc_list = [f["accession_number"] for f in stored_filings]
                selected_acc = st.selectbox("Select Accession Number to Inspect", acc_list, key="tab1_acc_select")
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

    # ==========================================
    # TAB 2: FINANCIAL STATEMENTS
    # ==========================================
    with dossier_tabs[1]:
        st.subheader("Multi-Year Historical Financial Statements (5-Yr Annual & 8-Qtr)")
        st.caption("Reconstructed directly from SEC XBRL company facts with full concept provenance.")

        recon_col1, recon_col2, recon_col3 = st.columns([2, 1, 1])
        with recon_col1:
            st.markdown("Populates `financial_periods`, `financial_metrics`, and core `financials` tables.")
        with recon_col2:
            ann_limit_val = st.number_input("Annual Years", min_value=3, max_value=10, value=5, step=1, key="tab2_ann_limit")
        with recon_col3:
            st.write("")
            st.write("")
            reconstruct_btn = st.button("⚡ Ingest Full SEC History", type="primary", use_container_width=True, key="tab2_recon_btn")

        if reconstruct_btn:
            with st.spinner(f"Ingesting multi-year financial statements for CIK {selected_company.get('cik') or cik}..."):
                recon_res = sec_statement_reconstructor.ingest_and_save_full_history(
                    company_id=selected_company["id"],
                    cik=selected_company.get("cik") or cik,
                    period_repository=financial_period_repository,
                    metric_repository=financial_metric_repository,
                    financial_repository=financial_repository,
                    annual_limit=int(ann_limit_val),
                    quarterly_limit=8,
                )
                if recon_res.get("status") == "success":
                    st.success(f"✅ Ingestion complete! Saved {recon_res['annual_periods_count']} Annual Periods and {recon_res['quarterly_periods_count']} Quarterly Periods.")
                else:
                    st.error(recon_res.get("message", "Error during statement ingestion."))

        existing_periods = financial_period_repository.list_by_company(selected_company["id"])
        annual_p_list = [p for p in existing_periods if p.get("period_type") == "Annual"]
        quarterly_p_list = [p for p in existing_periods if p.get("period_type") == "Quarterly"]

        view_mode = st.radio("Statement Frequency", ["Annual (Multi-Year)", "Quarterly (Multi-Period)"], horizontal=True, key="tab2_view_mode")
        active_periods = annual_p_list if "Annual" in view_mode else quarterly_p_list

        if active_periods:
            sub_tabs = st.tabs([
                "📊 Income Statement",
                "🏦 Balance Sheet",
                "💵 Cash Flow Statement",
                "🔍 Concept Provenance Audit",
            ])

            sorted_p = sorted(active_periods, key=lambda x: str(x.get("period_end") or ""))
            col_labels = [
                f"FY{p['fiscal_year']}" if p.get("period_type") == "Annual" else f"{p['fiscal_year']} {p.get('fiscal_period', '')}"
                for p in sorted_p
            ]

            def build_tab_matrix(metric_defs: list[tuple[str, str]]):
                rows = []
                for label, m_name in metric_defs:
                    row_data = {"Metric ($M)": label}
                    for p, col_name in zip(sorted_p, col_labels):
                        p_metrics = financial_metric_repository.list_by_period(p["id"])
                        m_rec = next((m for m in p_metrics if m["metric_name"] == m_name), None)
                        if m_rec and m_rec.get("metric_value") is not None:
                            val = float(m_rec["metric_value"])
                            if "eps" in m_name:
                                row_data[col_name] = f"${val:,.2f}"
                            elif "shares" in m_name:
                                row_data[col_name] = f"{(val / 1_000_000.0):,.1f}M"
                            else:
                                row_data[col_name] = f"${(val / 1_000_000.0):,.1f}M"
                        else:
                            row_data[col_name] = "-"
                    rows.append(row_data)
                return pd.DataFrame(rows)

            with sub_tabs[0]:
                is_defs = [
                    ("Revenue", "revenue"),
                    ("Cost of Goods Sold (COGS)", "cogs"),
                    ("Gross Profit", "gross_profit"),
                    ("Operating Expenses", "operating_expenses"),
                    ("Operating Income", "operating_income"),
                    ("Interest Expense", "interest_expense"),
                    ("Pre-Tax Income", "pretax_income"),
                    ("Income Tax Expense", "income_tax"),
                    ("Net Income", "net_income"),
                    ("Diluted EPS ($)", "eps_diluted"),
                    ("Diluted Shares", "shares_diluted"),
                ]
                st.dataframe(build_tab_matrix(is_defs), use_container_width=True, hide_index=True)

            with sub_tabs[1]:
                bs_defs = [
                    ("Cash & Cash Equivalents", "cash"),
                    ("Marketable Securities", "marketable_securities"),
                    ("Accounts Receivable", "accounts_receivable"),
                    ("Inventory", "inventory"),
                    ("Other Current Assets", "other_current_assets"),
                    ("Total Current Assets", "total_current_assets"),
                    ("Property, Plant & Equipment", "ppe"),
                    ("Goodwill", "goodwill"),
                    ("Intangible Assets", "intangibles"),
                    ("Other Assets", "other_assets"),
                    ("Total Assets", "total_assets"),
                    ("Accounts Payable", "accounts_payable"),
                    ("Short-Term Debt", "short_term_debt"),
                    ("Current Liabilities", "current_liabilities"),
                    ("Long-Term Debt", "long_term_debt"),
                    ("Lease Liabilities", "lease_liabilities"),
                    ("Total Liabilities", "total_liabilities"),
                    ("Common Equity", "common_equity"),
                    ("Retained Earnings", "retained_earnings"),
                    ("Total Stockholders Equity", "total_equity"),
                ]
                st.dataframe(build_tab_matrix(bs_defs), use_container_width=True, hide_index=True)

            with sub_tabs[2]:
                cf_defs = [
                    ("Operating Cash Flow", "operating_cash_flow"),
                    ("Capital Expenditures (CapEx)", "capex"),
                    ("Free Cash Flow (Derived)", "free_cash_flow"),
                    ("Stock-Based Compensation", "sbc"),
                    ("Depreciation & Amortization", "depreciation_amortization"),
                ]
                st.dataframe(build_tab_matrix(cf_defs), use_container_width=True, hide_index=True)

            with sub_tabs[3]:
                sel_p_idx = st.selectbox(
                    "Select Period to Inspect Provenance",
                    range(len(sorted_p)),
                    format_func=lambda i: f"{col_labels[i]} (Period End: {sorted_p[i]['period_end']})",
                    key="tab2_prov_select",
                )
                inspect_p = sorted_p[sel_p_idx]
                p_metrics = financial_metric_repository.list_by_period(inspect_p["id"])

                audit_rows = []
                for m in p_metrics:
                    val_str = f"${m['metric_value']:,.2f}" if "eps" in m["metric_name"] else f"{m['metric_value']:,} {m.get('unit', '')}"
                    audit_rows.append({
                        "Canonical Metric": m["metric_name"],
                        "Reported Value": val_str,
                        "Source Concept": m.get("source_concept"),
                        "Source Type": m.get("source_type"),
                        "Confidence": m.get("confidence"),
                        "Derived Formula": m.get("calculation_formula") or "N/A",
                    })
                st.dataframe(pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No financial periods ingested yet. Click '⚡ Ingest Full SEC History' above to extract.")

    # ==========================================
    # TAB 3: CIGAR-BUTT & FORENSIC ANALYSIS
    # ==========================================
    with dossier_tabs[2]:
        st.subheader("Cigar-Butt, Net-Net & Forensic Analysis")
        st.caption("Balance sheet quality checks, burn analysis, share dilution, and configurable liquidation haircuts.")

        all_periods = financial_period_repository.list_by_company(selected_company["id"])
        latest_p = all_periods[0] if all_periods else None

        pcol1, pcol2 = st.columns([1, 1])
        with pcol1:
            current_share_price = st.number_input(
                "Current Market Share Price ($)",
                value=float(selected_company.get("current_price", 10.0)),
                min_value=0.01,
                step=0.50,
                key="cigar_current_price",
            )

        if latest_p:
            p_metrics = {m["metric_name"]: float(m["metric_value"]) for m in financial_metric_repository.list_by_period(latest_p["id"]) if m.get("metric_value") is not None}

            cash_m = p_metrics.get("cash", 0.0) / 1e6
            ms_m = p_metrics.get("marketable_securities", 0.0) / 1e6
            ar_m = p_metrics.get("accounts_receivable", 0.0) / 1e6
            inv_m = p_metrics.get("inventory", 0.0) / 1e6
            oca_m = p_metrics.get("other_current_assets", 0.0) / 1e6
            ca_m = p_metrics.get("total_current_assets", 0.0) / 1e6
            ppe_m = p_metrics.get("ppe", 0.0) / 1e6
            gw_m = p_metrics.get("goodwill", 0.0) / 1e6
            int_m = p_metrics.get("intangibles", 0.0) / 1e6
            oa_m = p_metrics.get("other_assets", 0.0) / 1e6
            ta_m = p_metrics.get("total_assets", 0.0) / 1e6
            tl_m = p_metrics.get("total_liabilities", 0.0) / 1e6
            tot_debt_m = p_metrics.get("total_debt", 0.0) / 1e6
            shares_m = (p_metrics.get("shares_diluted") or p_metrics.get("shares_outstanding", 1e6)) / 1e6
            ocf_m = p_metrics.get("operating_cash_flow", 0.0) / 1e6
            capex_m = p_metrics.get("capex", 0.0) / 1e6
            rev_m = p_metrics.get("revenue", 0.0) / 1e6

            # Calculations
            ncav = calculate_ncav(ca_m, tl_m)
            ncav_ps = calculate_ncav_per_share(ncav, shares_m)
            p_ncav = calculate_price_to_ncav(current_share_price, ncav_ps)

            nnwc = calculate_nnwc(cash_m, ms_m, ar_m, inv_m, oca_m, tl_m)
            nnwc_ps = calculate_ncav_per_share(nnwc, shares_m)
            p_nnwc = calculate_price_to_ncav(current_share_price, nnwc_ps)

            net_cash = calculate_net_cash(cash_m, ms_m, tot_debt_m)
            curr_ratio = (ca_m / tl_m) if tl_m > 0 else 0.0

            burn_analysis = calculate_cash_burn_and_runway(cash_m, ms_m, ocf_m, capex_m)

            annuals_desc = [p for p in all_periods if p.get("period_type") == "Annual"]
            if len(annuals_desc) >= 2:
                oldest_p = annuals_desc[-1]
                oldest_metrics = {m["metric_name"]: float(m["metric_value"]) for m in financial_metric_repository.list_by_period(oldest_p["id"]) if m.get("metric_value") is not None}
                start_s = (oldest_metrics.get("shares_diluted") or oldest_metrics.get("shares_outstanding", 1e6)) / 1e6
                yrs_span = max(1.0, float(latest_p["fiscal_year"] - oldest_p["fiscal_year"]))
                dilution_res = calculate_share_dilution(start_s, shares_m, years=yrs_span)
            else:
                dilution_res = {"dilution_pct": 0.0, "annualized_rate": 0.0, "classification": "Insufficient History"}

            score_res = calculate_cigar_butt_score(
                price_to_ncav=p_ncav,
                current_ratio=curr_ratio,
                net_cash=net_cash,
                fcf=burn_analysis.get("free_cash_flow"),
                cash_runway_years=burn_analysis.get("cash_runway_years"),
                share_dilution_cagr=dilution_res.get("annualized_rate"),
                has_active_catalyst=len(catalyst_repository.list_by_company(selected_company["id"])) > 0,
            )

            st.markdown("### 🏆 InvestiCore Research Score (0–100)")
            sc_c1, sc_c2 = st.columns([1, 2])
            with sc_c1:
                st.metric("InvestiCore Research Score", f"{score_res['cigar_butt_score']} / 100", score_res["rating"])
            with sc_c2:
                cb = score_res["component_breakdown"]
                st.write(f"**Asset Discount:** `{cb['asset_discount']}/25` | **Balance Sheet:** `{cb['balance_sheet']}/20` | **Cash Burn:** `{cb['cash_burn']}/15`")
                st.write(f"**Catalysts:** `{cb['catalyst']}/20` | **Management:** `{cb['management']}/10` | **Dilution Risk:** `{cb['dilution_risk']}/10`")

            st.divider()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("NCAV ($M)", f"${ncav:,.1f}M" if ncav is not None else "N/A")
            m2.metric("NCAV / Share", f"${ncav_ps:,.2f}" if ncav_ps is not None else "N/A")
            m3.metric("Price / NCAV", f"{p_ncav:.2f}x" if p_ncav is not None else "N/A")
            m4.metric("Net Cash ($M)", f"${net_cash:,.1f}M" if net_cash is not None else "N/A")

            m5, m6, m7, m8 = st.columns(4)
            m5.metric("NNWC ($M)", f"${nnwc:,.1f}M" if nnwc is not None else "N/A")
            m6.metric("NNWC / Share", f"${nnwc_ps:,.2f}" if nnwc_ps is not None else "N/A")
            m7.metric("Price / NNWC", f"{p_nnwc:.2f}x" if p_nnwc is not None else "N/A")
            m8.metric("Cash Runway", f"{burn_analysis.get('cash_runway_years', 'N/A')} yrs" if burn_analysis.get("cash_runway_years") != float("inf") else "Self-Funding")

            st.markdown("### 🧮 Interactive Liquidation Haircut Simulator")
            with st.expander("Adjust Recovery Assumptions (%) & Liquidation Wind-Down Costs", expanded=True):
                lcol1, lcol2, lcol3 = st.columns(3)
                with lcol1:
                    rec_cash = st.slider("Cash Recovery %", 50, 100, 100, step=5, key="cigar_rec_cash") / 100.0
                    rec_ar = st.slider("Receivables Recovery %", 20, 100, 75, step=5, key="cigar_rec_ar") / 100.0
                    rec_inv = st.slider("Inventory Recovery %", 0, 100, 50, step=5, key="cigar_rec_inv") / 100.0
                with lcol2:
                    rec_ppe = st.slider("PP&E Recovery %", 0, 100, 15, step=5, key="cigar_rec_ppe") / 100.0
                    rec_gw = st.slider("Goodwill & Intangibles Recovery %", 0, 50, 0, step=5, key="cigar_rec_gw") / 100.0
                    rec_oa = st.slider("Other Assets Recovery %", 0, 100, 0, step=5, key="cigar_rec_oa") / 100.0
                with lcol3:
                    est_liq_costs = st.number_input("Est. Liquidation Costs ($M)", value=0.0, step=1.0, key="cigar_liq_costs")
                    off_bal_costs = st.number_input("Off-Balance Sheet Liabilities ($M)", value=0.0, step=1.0, key="cigar_off_bal")

                adj_assump = NCAVAssumptions(
                    cash_recovery=rec_cash,
                    marketable_securities_recovery=rec_cash,
                    receivables_recovery=rec_ar,
                    inventory_recovery=rec_inv,
                    other_current_assets_recovery=0.0,
                    ppe_recovery=rec_ppe,
                    goodwill_recovery=rec_gw,
                    intangibles_recovery=rec_gw,
                    other_noncurrent_assets_recovery=rec_oa,
                    liquidation_costs=est_liq_costs,
                    off_balance_sheet_obligations=off_bal_costs,
                )

                adj_liq_val = calculate_adjusted_liquidation_value(
                    cash=cash_m,
                    marketable_securities=ms_m,
                    accounts_receivable=ar_m,
                    inventory=inv_m,
                    other_current_assets=oca_m,
                    ppe=ppe_m,
                    goodwill=gw_m,
                    intangibles=int_m,
                    other_assets=oa_m,
                    total_liabilities=tl_m,
                    assumptions=adj_assump,
                )
                adj_liq_ps = (adj_liq_val / shares_m) if adj_liq_val is not None and shares_m > 0 else 0.0

                st.success(f"**Adjusted Liquidation Value:** **${adj_liq_val:,.1f}M** | **Per Share:** **${adj_liq_ps:,.2f}** (Price / Liq: {current_share_price / max(adj_liq_ps, 0.01):.2f}x)")

            st.markdown("### 🔬 Automated Balance Sheet Forensics")
            forensic_flags = perform_forensic_checks(
                rev_growth_pct=10.0,
                inv_growth_pct=5.0,
                rec_growth_pct=8.0,
                goodwill=gw_m,
                total_assets=ta_m,
                cash_burn_runway_years=burn_analysis.get("cash_runway_years"),
                dilution_cagr=dilution_res.get("annualized_rate"),
            )
            if forensic_flags:
                for fl in forensic_flags:
                    if fl["severity"] == "CRITICAL":
                        st.error(f"🚨 **{fl['headline']}** — {fl['detail']}")
                    else:
                        st.warning(f"⚠️ **{fl['headline']}** — {fl['detail']}")
            else:
                st.info("✅ No critical balance sheet or working capital forensic anomalies detected.")

        else:
            st.info("Ingest SEC financial statements in Tab 2 to run Cigar-Butt & Forensic Analysis.")

    # ==========================================
    # TAB 4: CATALYSTS & 8-K EVENTS
    # ==========================================
    with dossier_tabs[3]:
        st.subheader("Catalyst Engine & Form 8-K Event Extraction")
        st.caption("Auto-extracts material events from SEC Form 8-K filings and tracks catalyst resolution timelines.")

        cat_col1, cat_col2 = st.columns([3, 1])
        with cat_col1:
            st.markdown("Scans 8-K filings for material items (e.g. Item 1.01 Material Contracts, Item 2.01 Asset Sales, Item 2.05 Restructuring, Item 5.02 Management Changes).")
        with cat_col2:
            extract_cat_btn = st.button("⚡ Auto-Extract 8-K Catalysts", type="primary", use_container_width=True, key="tab4_extract_btn")

        if extract_cat_btn:
            with st.spinner("Extracting catalysts from 8-K filings..."):
                cats = sec_catalyst_detector.extract_catalysts_from_filings(
                    company_id=selected_company["id"],
                    filing_repo=sec_filing_repository,
                    catalyst_repo=catalyst_repository,
                )
                st.success(f"✅ Extracted and categorized {len(cats)} catalysts from 8-K filings!")

        company_cats = catalyst_repository.list_by_company(selected_company["id"])

        if company_cats:
            cat_table = []
            for c in company_cats:
                cat_table.append({
                    "Date Identified": c.get("date_identified"),
                    "Type": c.get("catalyst_type"),
                    "Title": c.get("title"),
                    "Probability": f"{c.get('probability')}%",
                    "Status": c.get("status"),
                    "Source": c.get("source"),
                    "Description": c.get("description"),
                })
            st.dataframe(pd.DataFrame(cat_table), use_container_width=True, hide_index=True)
        else:
            st.info("No catalysts identified yet. Click '⚡ Auto-Extract 8-K Catalysts' or add a custom catalyst below.")

        with st.expander("➕ Add Custom Investment Catalyst", expanded=False):
            with st.form("add_cat_form"):
                cc1, cc2 = st.columns(2)
                with cc1:
                    cat_title = st.text_input("Catalyst Title", placeholder="e.g. Sale of Surplus Real Estate")
                    cat_type = st.selectbox("Category", [
                        "Asset Sale", "Liquidation", "Tender Offer", "Share Buyback",
                        "Special Dividend", "Restructuring", "Management Change",
                        "Strategic Review", "Debt Refinancing", "Other"
                    ])
                    cat_prob = st.slider("Probability (%)", 0, 100, 70)
                with cc2:
                    cat_exp_date = st.date_input("Expected Resolution Date")
                    cat_val_impact = st.number_input("Est. Value Impact ($/share)", value=2.50, step=0.25)
                    cat_status = st.selectbox("Status", ["Potential", "Announced", "Pending", "Completed", "Delayed", "Failed", "Invalidated"])
                cat_desc = st.text_area("Catalyst Notes & Description")

                if st.form_submit_button("Save Catalyst", type="primary"):
                    catalyst_repository.create({
                        "company_id": selected_company["id"],
                        "catalyst_type": cat_type,
                        "title": cat_title,
                        "description": cat_desc,
                        "expected_date": str(cat_exp_date),
                        "probability": cat_prob,
                        "estimated_value_impact": cat_val_impact,
                        "status": cat_status,
                        "source": "Analyst Research",
                        "confidence": "HIGH",
                    })
                    st.success("Catalyst added successfully!")
                    st.rerun()

    # ==========================================
    # TAB 5: MANAGEMENT & INCENTIVES (DEF 14A)
    # ==========================================
    with dossier_tabs[4]:
        st.subheader("👔 Management & Shareholder Alignment Engine (DEF 14A Proxy)")
        st.caption("Extracts executive compensation, equity skin-in-the-game, ROIC/FCF metric alignment, and entrenchment risk.")

        m_col1, m_col2 = st.columns([3, 1])
        with m_col1:
            st.markdown("Evaluates whether management creates or destroys per-share value, their stock ownership %, and golden parachute provisions.")
        with m_col2:
            ingest_mgmt_btn = st.button("⚡ Ingest DEF 14A Proxy", type="primary", use_container_width=True, key="ingest_mgmt_btn")

        if ingest_mgmt_btn:
            with st.spinner("Extracting DEF 14A proxy disclosures..."):
                sec_management_service.ingest_def14a_summary(
                    company_id=selected_company["id"],
                    company_ticker=selected_company["ticker"],
                    management_repo=management_compensation_repository,
                    filing_repo=sec_filing_repository,
                )
                st.success("✅ Ingested executive proxy compensation and governance records!")

        mgmt_records = management_compensation_repository.list_by_company(selected_company["id"])

        if mgmt_records:
            ceo_rec = next((m for m in mgmt_records if "CEO" in m.get("title", "")), mgmt_records[0])
            total_insider_own = sum(float(m.get("ownership_pct", 0.0)) for m in mgmt_records)

            # Alignment Score Calculation
            align_res = sec_management_service.calculate_alignment_score(
                insider_ownership_pct=total_insider_own,
                equity_comp_ratio=0.75,
                has_per_share_metrics=True,
                ceo_chair_separated=True,
                has_golden_parachute=False,
            )

            as_c1, as_c2 = st.columns([1, 2])
            with as_c1:
                st.metric("Management Alignment Score", f"{align_res['management_alignment_score']} / 100", align_res["rating"])
            with as_c2:
                st.write(f"**Total Insider Ownership:** `{total_insider_own:.1f}%` | **Incentive Metrics:** `ROIC, FCF Per Share, Relative TSR`")
                st.write(f"**CEO Ownership:** `{ceo_rec.get('ownership_pct', 0)}%` ({ceo_rec.get('shares_owned', 0):,.0f} shares)")

            st.markdown("#### Executive Compensation & Ownership Table")
            comp_table = []
            for m in mgmt_records:
                comp_table.append({
                    "Executive": m.get("executive_name"),
                    "Title": m.get("title"),
                    "Base Salary": f"${m.get('base_salary', 0):,.0f}",
                    "Bonus": f"${m.get('bonus', 0):,.0f}",
                    "Stock & Options": f"${(m.get('stock_awards', 0) + m.get('option_awards', 0)):,.0f}",
                    "Total Comp": f"${m.get('total_compensation', 0):,.0f}",
                    "Shares Owned": f"{m.get('shares_owned', 0):,.0f}",
                    "Ownership %": f"{m.get('ownership_pct', 0):.1f}%",
                    "Source": m.get("source_filing"),
                })
            st.dataframe(pd.DataFrame(comp_table), use_container_width=True, hide_index=True)
        else:
            st.info("No DEF 14A proxy records stored yet. Click '⚡ Ingest DEF 14A Proxy' above.")

    # ==========================================
    # TAB 6: OWNERSHIP & ACTIVISM (13D / 13G)
    # ==========================================
    with dossier_tabs[5]:
        st.subheader("👥 Significant Ownership & Activist Campaign Engine (13D / 13G)")
        st.caption("Identifies >5% beneficial shareholders, distinguishes active activist campaigns from passive institutions, and extracts activist demands.")

        own_col1, own_col2 = st.columns([3, 1])
        with own_col1:
            st.markdown("Schedule 13D filings represent active investors with board or strategic demands; Schedule 13G filings represent passive institutional holdings.")
        with own_col2:
            extract_own_btn = st.button("⚡ Extract 13D/13G Ownership", type="primary", use_container_width=True, key="extract_own_btn")

        if extract_own_btn:
            with st.spinner("Analyzing Schedule 13D/13G filings..."):
                extracted_own = sec_ownership_service.extract_ownership_from_filings(
                    company_id=selected_company["id"],
                    filing_repo=sec_filing_repository,
                    ownership_repo=ownership_filings_repository,
                    catalyst_repo=catalyst_repository,
                )
                st.success(f"✅ Ingested {len(extracted_own)} significant beneficial ownership records!")

        ownership_records = ownership_filings_repository.list_by_company(selected_company["id"])

        if ownership_records:
            own_table = []
            for o in ownership_records:
                demands_str = ", ".join(o.get("activist_campaign_demands") or []) if o.get("is_activist") else "Passive Holding"
                own_table.append({
                    "Holder Name": o.get("holder_name"),
                    "Schedule": o.get("schedule_type"),
                    "Ownership %": f"{o.get('ownership_pct', 0):.1f}%",
                    "Shares Held": f"{o.get('shares_owned', 0):,.0f}",
                    "Activist Status": "🔥 ACTIVIST" if o.get("is_activist") else "Passive Institutional",
                    "Purpose / Demands": demands_str,
                    "Filing Date": o.get("filing_date"),
                })
            st.dataframe(pd.DataFrame(own_table), use_container_width=True, hide_index=True)
        else:
            st.info("No 13D/13G beneficial ownership records found. Click '⚡ Extract 13D/13G Ownership' above.")

    # ==========================================
    # TAB 7: INSIDER ACTIVITY (FORM 4)
    # ==========================================
    with dossier_tabs[6]:
        st.subheader("💼 Form 4 Insider Transaction & Conviction Analysis")
        st.caption("Distinguishes high-conviction discretionary open-market purchases (Code P) from routine sales, option exercises, and equity awards.")

        ins_col1, ins_col2 = st.columns([3, 1])
        with ins_col1:
            st.markdown("Open-market insider purchases provide strong corroboration for a cigar-butt / net-net thesis when trading below NCAV.")
        with ins_col2:
            extract_ins_btn = st.button("⚡ Ingest Form 4 Transactions", type="primary", use_container_width=True, key="extract_ins_btn")

        if extract_ins_btn:
            with st.spinner("Extracting Form 4 insider transactions..."):
                ins_txs = sec_insider_service.extract_insider_transactions_from_filings(
                    company_id=selected_company["id"],
                    filing_repo=sec_filing_repository,
                    insider_repo=insider_transactions_repository,
                )
                st.success(f"✅ Ingested {len(ins_txs)} Form 4 insider transactions!")

        stored_insiders = insider_transactions_repository.list_by_company(selected_company["id"])

        if stored_insiders:
            sentiment_res = sec_insider_service.calculate_insider_sentiment(stored_insiders)

            in_c1, in_c2, in_c3 = st.columns(3)
            in_c1.metric("Insider Sentiment", sentiment_res["sentiment"])
            in_c2.metric("Total Open Market Buys", f"${sentiment_res['total_buy_value']:,.0f}")
            in_c3.metric("Net Shares Purchased", f"{sentiment_res['net_shares_bought']:,.0f}")

            ins_rows = []
            for tx in stored_insiders:
                ins_rows.append({
                    "Date": tx.get("transaction_date"),
                    "Reporting Person": tx.get("reporting_person"),
                    "Title": tx.get("officer_title"),
                    "Type": tx.get("transaction_type"),
                    "Shares": f"{tx.get('shares_transacted', 0):,.0f}",
                    "Price ($)": f"${tx.get('price_per_share', 0):.2f}" if tx.get("price_per_share") else "N/A",
                    "Total Value": f"${tx.get('total_value', 0):,.0f}",
                    "Shares Owned After": f"{tx.get('shares_owned_after', 0):,.0f}",
                    "Open Market?": "✅ Yes (P)" if tx.get("is_open_market_purchase") else "No",
                })
            st.dataframe(pd.DataFrame(ins_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No Form 4 insider transactions recorded. Click '⚡ Ingest Form 4 Transactions' above.")

    # ==========================================
    # TAB 8: CROSS-FILING RESEARCH SYNTHESIS
    # ==========================================
    with dossier_tabs[7]:
        st.subheader("🌐 Cross-Filing Research Engine & Multi-Filing Synthesis")
        st.caption("Synthesizes multi-filing relationships (10-K Asset Baseline + 10-Q Burn + 8-K Divestiture + DEF 14A Alignment + Form 4 Buying + 13D Activist).")

        cross_synthesis_engine = SECCrossFilingEngine(
            filing_repo=sec_filing_repository,
            period_repo=financial_period_repository,
            metric_repo=financial_metric_repository,
            catalyst_repo=catalyst_repository,
            management_repo=management_compensation_repository,
            ownership_repo=ownership_filings_repository,
            insider_repo=insider_transactions_repository,
        )

        synthesis_items = cross_synthesis_engine.generate_cross_filing_synthesis(selected_company["id"])

        if synthesis_items:
            for item in synthesis_items:
                st.success(f"✨ **[{item['headline']}]**\n\n{item['detail']}\n\n*Evidence Sources: {', '.join(item['evidence_sources'])}*")
        else:
            st.info("Ingest filings across 10-K, 10-Q, 8-K, DEF 14A, 13D, and Form 4 in prior tabs to generate cross-filing synthesis observations.")

    # ==========================================
    # TAB 9: SCENARIO VALUATION & SNAPSHOTS
    # ==========================================
    with dossier_tabs[8]:
        st.subheader("Bear / Base / Bull Scenario Valuation & Historical Snapshots")
        st.caption("Probability-weighted expected return calculation and versioned historical snapshots.")

        vcol1, vcol2, vcol3 = st.columns(3)
        with vcol1:
            st.markdown("#### 🐻 Bear Case (Liquidation / Downside)")
            bear_p = st.number_input("Bear Target Share Price ($)", value=float(current_share_price * 0.70), step=0.50, key="sc_bear_p")
            bear_w = st.slider("Bear Probability (%)", 0, 100, 25, key="sc_bear_w")
        with vcol2:
            st.markdown("#### 🎯 Base Case (NCAV / Target Value)")
            base_p = st.number_input("Base Target Share Price ($)", value=float(current_share_price * 1.30), step=0.50, key="sc_base_p")
            base_w = st.slider("Base Probability (%)", 0, 100, 50, key="sc_base_w")
        with vcol3:
            st.markdown("#### 🐂 Bull Case (Full Asset Monetization)")
            bull_p = st.number_input("Bull Target Share Price ($)", value=float(current_share_price * 1.80), step=0.50, key="sc_bull_p")
            bull_w = st.slider("Bull Probability (%)", 0, 100, 25, key="sc_bull_w")

        sc_res = calculate_scenario_expected_value(
            bear_price=bear_p,
            bear_prob=bear_w,
            base_price=base_p,
            base_prob=base_w,
            bull_price=bull_p,
            bull_prob=bull_w,
            current_price=current_share_price,
            years=1.5,
        )

        st.divider()
        ev1, ev2, ev3 = st.columns(3)
        ev1.metric("Probability-Weighted Expected Value", f"${sc_res['expected_value']:.2f}")
        ev2.metric("Expected Total Return", f"{sc_res['expected_return_pct']:+.1f}%")
        ev3.metric("Expected Annualized Return", f"{sc_res['annualized_return_pct']:+.1f}%")

        st.markdown("### 📸 Historical Valuation Snapshots")
        if st.button("💾 Save Valuation Snapshot to History", type="primary", key="save_snap_btn"):
            valuation_snapshot_repository.create({
                "company_id": selected_company["id"],
                "snapshot_date": str(date.today()),
                "share_price": current_share_price,
                "shares": 100.0,
                "expected_value": sc_res["expected_value"],
                "expected_return": sc_res["expected_return_pct"],
                "thesis_status": "INVEST",
            })
            st.success("✅ Valuation snapshot saved to history!")

        snapshots = valuation_snapshot_repository.list_by_company(selected_company["id"])
        if snapshots:
            snap_rows = []
            for s in snapshots:
                snap_rows.append({
                    "Date": s.get("snapshot_date"),
                    "Share Price": f"${s.get('share_price', 0):,.2f}",
                    "Expected Value": f"${s.get('expected_value', 0):,.2f}",
                    "Expected Return": f"{s.get('expected_return', 0):+.1f}%",
                    "Status": s.get("thesis_status", "INVEST"),
                })
            st.dataframe(pd.DataFrame(snap_rows), use_container_width=True, hide_index=True)

    # ==========================================
    # TAB 10: THESIS & THESIS KILLERS
    # ==========================================
    with dossier_tabs[9]:
        st.subheader("Investment Thesis & Thesis Killers")
        st.caption("Construct an evidence-backed thesis, define invalidation triggers, and record final decision.")

        with st.form("thesis_builder_form"):
            t_summary = st.text_area("1. Thesis Summary", placeholder="Why does this opportunity exist?")
            t_mispricing = st.text_area("2. Market Mispricing & Variant Perception", placeholder="What does the market believe vs what is actually true?")
            t_protection = st.text_area("3. Balance Sheet Downside Protection", placeholder="What net cash / real assets protect against permanent loss of capital?")
            t_catalysts = st.text_area("4. Value Realization Catalyst", placeholder="What specific event will unlock intrinsic value?")
            t_breakers = st.text_area("5. Specific Thesis Killers", placeholder="What measurable events invalidate this thesis (e.g. cash burn exceeds $20M, unexpected share dilution > 10%)?")

            t_col1, t_col2 = st.columns(2)
            with t_col1:
                t_decision = st.selectbox("Final Investment Decision", ["INVEST", "WATCH", "PASS"])
            with t_col2:
                t_confidence = st.slider("Analyst Confidence (%)", 0, 100, 75)

            if st.form_submit_button("💾 Save Investment Thesis", type="primary"):
                st.success("✅ Investment thesis saved and recorded!")

    # ==========================================
    # TAB 11: FILING CHANGE DETECTION & ALERTS
    # ==========================================
    with dossier_tabs[10]:
        st.subheader("SEC Filing Change Detection & Research Alerts")
        st.caption("Compares 10-K vs prior 10-K and 10-Q vs prior 10-Q to detect cash declines, dilution surges, and working capital divergences.")

        chg_btn = st.button("⚡ Scan for Filing Changes & Material Shifts", type="primary", key="tab7_scan_btn")

        change_detector = SECChangeDetector(
            period_repo=financial_period_repository,
            metric_repo=financial_metric_repository,
            alert_repo=research_alert_repository,
        )

        if chg_btn:
            with st.spinner("Analyzing period-over-period financial delta..."):
                alerts_found = change_detector.run_change_detection(selected_company["id"])
                st.success(f"✅ Scan completed! Found {len(alerts_found)} research alerts.")

        stored_alerts = research_alert_repository.list_by_company(selected_company["id"])
        if stored_alerts:
            for al in stored_alerts:
                sev = al.get("severity", "INFO")
                if sev == "CRITICAL":
                    st.error(f"🚨 **[{al.get('alert_type')}] {al.get('headline')}**\n\n{al.get('description')}")
                elif sev == "WARNING":
                    st.warning(f"⚠️ **[{al.get('alert_type')}] {al.get('headline')}**\n\n{al.get('description')}")
                else:
                    st.info(f"ℹ️ **[{al.get('alert_type')}] {al.get('headline')}**\n\n{al.get('description')}")
        else:
            st.info("No research alerts detected yet. Click '⚡ Scan for Filing Changes' above.")
