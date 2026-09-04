import pandas as pd
import plotly.express as px
import streamlit as st

from database.store import add_company, company_repository, financial_repository

st.title("Company Records")
st.caption("Add, search, and track the companies you are researching")

import pandas as pd
import plotly.express as px
import streamlit as st

from database.store import add_company, company_repository, financial_repository
from services.financial_fetcher import fetch_company_profile, fetch_financial_history

st.title("Company Records")
st.caption("Add, search, and track the companies you are researching")

with st.expander("⚡ Auto-Fetch New Company & Financial Statements by Ticker", expanded=True):
    st.markdown("Enter a ticker symbol (e.g. `AAPL`, `MSFT`, `NVDA`, `AMZN`, `GOOGL`) to automatically fetch company profile metadata, market metrics, and historical financial statements.")
    col_auto1, col_auto2 = st.columns([3, 1])
    with col_auto1:
        auto_ticker = st.text_input("Stock Ticker Symbol", placeholder="e.g. NVDA", key="auto_ticker_input")
    with col_auto2:
        st.write("")
        st.write("")
        fetch_btn = st.button("⚡ Fetch & Save", type="primary", use_container_width=True)

    if fetch_btn:
        if not auto_ticker.strip():
            st.warning("Please enter a stock ticker symbol.")
        else:
            with st.spinner(f"Fetching profile and financial statements for {auto_ticker.upper()}..."):
                prof = fetch_company_profile(auto_ticker)
                if not prof:
                    st.error(f"Could not fetch company profile for '{auto_ticker.upper()}'. Please verify ticker symbol.")
                else:
                    existing = company_repository.get_by_ticker(prof["ticker"])
                    if existing:
                        comp_rec = company_repository.update(existing["id"], prof)
                        st.info(f"Updated existing record for {prof['name']} ({prof['ticker']}).")
                    else:
                        comp_rec = add_company(prof)
                        st.success(f"Created new company record for {prof['name']} ({prof['ticker']})!")

                    cid = comp_rec["id"]
                    hist = fetch_financial_history(prof["ticker"])
                    ann_count = len(hist.get("annual", []))
                    q_count = len(hist.get("quarterly", []))

                    for rec in hist.get("annual", []):
                        financial_repository.create_or_update(
                            cid,
                            rec["fiscal_year"],
                            rec,
                            period_type="Annual",
                            fiscal_quarter=None,
                        )

                    for rec in hist.get("quarterly", []):
                        financial_repository.create_or_update(
                            cid,
                            rec["fiscal_year"],
                            rec,
                            period_type="Quarterly",
                            fiscal_quarter=rec.get("fiscal_quarter"),
                        )

                    st.success(f"✅ Auto-fetched {ann_count} Annual Statements and {q_count} Quarterly Statements for {prof['name']}!")
                    st.rerun()

with st.expander("📝 Manual Add / Edit Company Profile", expanded=False):
    with st.form("company_form"):
        col1, col2 = st.columns(2)
        with col1:
            ticker = st.text_input("Ticker")
            name = st.text_input("Company name")
            sector = st.text_input("Sector")
            industry = st.text_input("Industry")
        with col2:
            country = st.text_input("Country")
            website = st.text_input("Website")
            status = st.selectbox("Status", ["Researching", "Watchlist", "Owned", "Buy Candidate", "Avoid", "Sold", "Archived"])
            description = st.text_area("Description")
        submitted = st.form_submit_button("Save company")
        if submitted:
            if not ticker or not name:
                st.warning("Ticker and company name are required.")
            else:
                add_company(
                    {
                        "ticker": ticker.upper(),
                        "name": name,
                        "sector": sector,
                        "industry": industry,
                        "country": country,
                        "website": website,
                        "status": status,
                        "description": description,
                    }
                )
                st.success(f"Saved {name} ({ticker.upper()}).")

search = st.text_input("Search companies")
company_rows = company_repository.search(search) if search else company_repository.list_all()
if company_rows:
    st.dataframe(company_rows, use_container_width=True)

    st.divider()
    st.subheader("📊 Financial Data Entry & Historicals")

    selected_cid = st.selectbox(
        "Select Company to view or edit financials",
        [c["id"] for c in company_rows],
        format_func=lambda cid: next(f"{c['ticker']} - {c['name']}" for c in company_rows if c["id"] == cid),
    )

    if selected_cid:
        current_comp = next((c for c in company_rows if c["id"] == selected_cid), None)
        if current_comp:
            c_head1, c_head2 = st.columns([3, 1])
            with c_head1:
                st.caption(f"Sector: **{current_comp.get('sector', 'N/A')}** | Industry: **{current_comp.get('industry', 'N/A')}** | Website: {current_comp.get('website', 'N/A')}")
            with c_head2:
                if st.button("⚡ Refresh from Yahoo Finance", key=f"refresh_btn_{selected_cid}", use_container_width=True):
                    with st.spinner(f"Refreshing financials for {current_comp['ticker']}..."):
                        hist = fetch_financial_history(current_comp['ticker'])
                        for rec in hist.get("annual", []):
                            financial_repository.create_or_update(selected_cid, rec["fiscal_year"], rec, period_type="Annual", fiscal_quarter=None)
                        for rec in hist.get("quarterly", []):
                            financial_repository.create_or_update(selected_cid, rec["fiscal_year"], rec, period_type="Quarterly", fiscal_quarter=rec.get("fiscal_quarter"))
                        st.success(f"Refreshed financials for {current_comp['ticker']}!")
                        st.rerun()

        st.divider()
        st.subheader("⚙️ Financial Display Settings")
        c_u1, c_u2 = st.columns([2, 2])
        with c_u1:
            unit_choice = st.radio(
                "Display Currency Unit",
                ["Millions ($M)", "Billions ($B)", "Thousands ($K)"],
                horizontal=True,
                key="unit_radio",
            )
        with c_u2:
            show_growth = st.checkbox("Include Period-over-Period Growth % in Tables", value=True, key="growth_cols_cb")

        unit_scale_map = {
            "Millions ($M)": (1.0, "$M"),
            "Billions ($B)": (0.001, "$B"),
            "Thousands ($K)": (1000.0, "$K"),
        }
        scale_factor, unit_suffix = unit_scale_map[unit_choice]
        monetary_cols = ["revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow", "free_cash_flow", "capex", "rnd", "sbc", "cash", "debt"]

        def prepare_display_df(records_list: list[dict]):
            if not records_list:
                return pd.DataFrame()
            df = pd.DataFrame(records_list)
            for m_col in monetary_cols:
                if m_col in df.columns:
                    df[m_col] = (df[m_col] * scale_factor).round(2)

            if show_growth:
                for g_col in ["revenue", "gross_profit", "operating_income", "net_income", "eps", "operating_cash_flow", "free_cash_flow"]:
                    if g_col in df.columns:
                        pct = df[g_col].pct_change() * 100.0
                        df[f"{g_col}_growth_%"] = pct.round(2)
            return df

        tab_annual, tab_quarterly, tab_ttm = st.tabs(["📅 Annual Statements", "📆 Quarterly Statements", "📊 TTM Summary"])

        with tab_annual:
            fin_records = financial_repository.get_by_company(selected_cid, period_type="Annual")
            if fin_records:
                df_fin = prepare_display_df(fin_records)
                if "period_label" not in df_fin.columns and "fiscal_year" in df_fin.columns:
                    df_fin["period_label"] = df_fin["fiscal_year"].apply(lambda y: f"FY{y}")
                
                for col_name in ["revenue", "net_income", "operating_cash_flow", "free_cash_flow"]:
                    if col_name not in df_fin.columns:
                        df_fin[col_name] = 0.0

                display_cols = [c for c in ["period_label", "fiscal_year", "revenue", "revenue_growth_%", "gross_profit", "gross_profit_growth_%", "operating_income", "operating_income_growth_%", "net_income", "net_income_growth_%", "eps", "eps_growth_%", "operating_cash_flow", "operating_cash_flow_growth_%", "free_cash_flow", "free_cash_flow_growth_%", "capex", "cash", "debt"] if c in df_fin.columns]

                st.write(f"Historical Annual Financial Statements ({unit_suffix}):")
                st.dataframe(df_fin[display_cols], use_container_width=True)

                # Metric CAGR Summary Cards
                c_rev = financial_repository.calculate_historical_cagr(selected_cid, "revenue", period_type="Annual")
                c_net = financial_repository.calculate_historical_cagr(selected_cid, "net_income", period_type="Annual")
                c_fcf = financial_repository.calculate_historical_cagr(selected_cid, "free_cash_flow", period_type="Annual")
                c_eps = financial_repository.calculate_historical_cagr(selected_cid, "eps", period_type="Annual")

                cg1, cg2, cg3, cg4 = st.columns(4)
                with cg1:
                    st.metric("Annual Revenue CAGR", f"{c_rev:.2f}%" if c_rev is not None else "N/A")
                with cg2:
                    st.metric("Annual Net Income CAGR", f"{c_net:.2f}%" if c_net is not None else "N/A")
                with cg3:
                    st.metric("Annual FCF CAGR", f"{c_fcf:.2f}%" if c_fcf is not None else "N/A")
                with cg4:
                    st.metric("Annual EPS CAGR", f"{c_eps:.2f}%" if c_eps is not None else "N/A")

                try:
                    fig = px.bar(
                        df_fin,
                        x="period_label" if "period_label" in df_fin.columns else "fiscal_year",
                        y=["revenue", "net_income", "free_cash_flow"],
                        barmode="group",
                        title=f"Annual Revenue, Net Income & Free Cash Flow Trend ({unit_suffix})",
                        labels={"value": f"Amount ({unit_suffix})", "period_label": "Fiscal Period", "variable": "Metric"},
                    )
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as err:
                    st.warning(f"Could not render annual trend chart: {err}")
            else:
                st.info("No annual financial statement records entered for this company yet.")

        with tab_quarterly:
            q_records = financial_repository.get_by_company(selected_cid, period_type="Quarterly")
            if q_records:
                df_q = prepare_display_df(q_records)
                if "period_label" not in df_q.columns and "fiscal_year" in df_q.columns:
                    df_q["period_label"] = df_q.apply(lambda r: f"{r.get('fiscal_year', '')} Q{r.get('fiscal_quarter', '')}", axis=1)

                for col_name in ["revenue", "net_income", "free_cash_flow"]:
                    if col_name not in df_q.columns:
                        df_q[col_name] = 0.0

                display_cols_q = [c for c in ["period_label", "fiscal_year", "fiscal_quarter", "revenue", "revenue_growth_%", "gross_profit", "gross_profit_growth_%", "operating_income", "operating_income_growth_%", "net_income", "net_income_growth_%", "eps", "eps_growth_%", "free_cash_flow", "free_cash_flow_growth_%", "capex", "cash", "debt"] if c in df_q.columns]
                st.write(f"Historical Quarterly Financial Statements ({unit_suffix}):")
                st.dataframe(df_q[display_cols_q], use_container_width=True)

                # Quarterly Annualized CAGR Summary Cards
                cq_rev = financial_repository.calculate_historical_cagr(selected_cid, "revenue", period_type="Quarterly")
                cq_net = financial_repository.calculate_historical_cagr(selected_cid, "net_income", period_type="Quarterly")
                cq_fcf = financial_repository.calculate_historical_cagr(selected_cid, "free_cash_flow", period_type="Quarterly")
                cq_eps = financial_repository.calculate_historical_cagr(selected_cid, "eps", period_type="Quarterly")

                qg1, qg2, qg3, qg4 = st.columns(4)
                with qg1:
                    st.metric("Quarterly Revenue CAGR (Ann.)", f"{cq_rev:.2f}%" if cq_rev is not None else "N/A")
                with qg2:
                    st.metric("Quarterly Net Income CAGR (Ann.)", f"{cq_net:.2f}%" if cq_net is not None else "N/A")
                with qg3:
                    st.metric("Quarterly FCF CAGR (Ann.)", f"{cq_fcf:.2f}%" if cq_fcf is not None else "N/A")
                with qg4:
                    st.metric("Quarterly EPS CAGR (Ann.)", f"{cq_eps:.2f}%" if cq_eps is not None else "N/A")

                try:
                    fig_q = px.bar(
                        df_q,
                        x="period_label" if "period_label" in df_q.columns else "fiscal_year",
                        y=["revenue", "net_income", "free_cash_flow"],
                        barmode="group",
                        title=f"Quarterly Revenue, Net Income & Free Cash Flow Trend ({unit_suffix})",
                        labels={"value": f"Amount ({unit_suffix})", "period_label": "Fiscal Quarter", "variable": "Metric"},
                    )
                    st.plotly_chart(fig_q, use_container_width=True)
                except Exception as err:
                    st.warning(f"Could not render quarterly trend chart: {err}")
            else:
                st.info("No quarterly financial statement records entered for this company yet.")


        with tab_ttm:
            ttm_data = financial_repository.calculate_ttm(selected_cid)
            if ttm_data:
                st.subheader(f"Trailing Twelve Months (TTM) — {ttm_data.get('period_label')}")
                scaled_ttm = dict(ttm_data)
                for m_col in monetary_cols:
                    if m_col in scaled_ttm:
                        scaled_ttm[m_col] = round(scaled_ttm[m_col] * scale_factor, 2)

                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("TTM Revenue", f"{scaled_ttm['revenue']:,.2f} {unit_suffix}")
                with m2:
                    st.metric("TTM Net Income", f"{scaled_ttm['net_income']:,.2f} {unit_suffix}")
                with m3:
                    st.metric("TTM Free Cash Flow", f"{scaled_ttm['free_cash_flow']:,.2f} {unit_suffix}")
                with m4:
                    fcf_m = (ttm_data['free_cash_flow'] / ttm_data['revenue'] * 100) if ttm_data['revenue'] > 0 else 0.0
                    st.metric("TTM FCF Margin", f"{fcf_m:.2f}%")

                df_ttm = pd.DataFrame([scaled_ttm])
                display_ttm_cols = [c for c in ["period_label", "revenue", "gross_profit", "operating_income", "net_income", "eps", "free_cash_flow", "capex", "cash", "debt"] if c in df_ttm.columns]
                st.table(df_ttm[display_ttm_cols])
            else:
                st.info("Insufficient financial data to calculate TTM metrics.")

        # Interactive Custom Metric CAGR & Growth Analyzer Widget
        st.divider()
        with st.expander("📈 Custom Metric CAGR & Growth Rate Analyzer", expanded=True):
            st.markdown("Analyze CAGR % and Period-over-Period growth for any financial metric.")
            metric_options = {
                "Revenue": "revenue",
                "Gross Profit": "gross_profit",
                "Operating Income": "operating_income",
                "Net Income": "net_income",
                "Operating Cash Flow (OCF)": "operating_cash_flow",
                "Free Cash Flow (FCF)": "free_cash_flow",
                "Diluted EPS": "eps",
                "Capital Expenditures (CaPex)": "capex",
                "Research & Development (R&D)": "rnd",
                "Stock-Based Comp (SBC)": "sbc",
                "Cash & Equivalents": "cash",
                "Total Debt": "debt",
            }
            
            an_col1, an_col2 = st.columns(2)
            with an_col1:
                selected_metric_name = st.selectbox("Select Metric to Analyze", list(metric_options.keys()), key="analyzer_metric_sel")
                selected_metric_key = metric_options[selected_metric_name]
            with an_col2:
                selected_period_type = st.radio("Period Type", ["Annual", "Quarterly"], horizontal=True, key="analyzer_period_type")

            analyzer_records = financial_repository.get_by_company(selected_cid, period_type=selected_period_type)
            if len(analyzer_records) >= 2:
                labels = [r["period_label"] for r in analyzer_records]
                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    start_p = st.selectbox("Start Period", labels, index=0, key="analyzer_start_p")
                with p_col2:
                    end_p = st.selectbox("End Period", labels, index=len(labels) - 1, key="analyzer_end_p")

                start_idx = labels.index(start_p)
                end_idx = labels.index(end_p)

                if start_idx >= end_idx:
                    st.warning("Start period must come before end period to calculate CAGR.")
                else:
                    start_rec = analyzer_records[start_idx]
                    end_rec = analyzer_records[end_idx]

                    s_val_raw = float(start_rec.get(selected_metric_key, 0.0) or 0.0)
                    e_val_raw = float(end_rec.get(selected_metric_key, 0.0) or 0.0)

                    is_per_share = (selected_metric_key == "eps")
                    unit_label_str = "$" if is_per_share else unit_suffix
                    val_factor = 1.0 if is_per_share else scale_factor

                    s_val_disp = round(s_val_raw * val_factor, 2)
                    e_val_disp = round(e_val_raw * val_factor, 2)

                    years_diff = end_rec["fiscal_year"] - start_rec["fiscal_year"]
                    if selected_period_type == "Quarterly":
                        quarters_count = (end_idx - start_idx)
                        years_span = max(quarters_count / 4.0, 0.25)
                    else:
                        years_span = max(years_diff, 1)

                    # Calculations
                    note_msg = None
                    if s_val_raw > 0 and e_val_raw > 0 and years_span > 0:
                        calc_cagr = (((e_val_raw / s_val_raw) ** (1.0 / years_span)) - 1.0) * 100.0
                        cagr_str = f"{calc_cagr:.2f}%"
                    elif s_val_raw < 0 and e_val_raw > 0 and years_span > 0:
                        calc_cagr = (((e_val_raw - s_val_raw) / abs(s_val_raw)) / years_span) * 100.0
                        cagr_str = f"{calc_cagr:+.2f}%"
                        note_msg = "ℹ️ Turnaround detected (started in loss, ended in profit). Displaying Annualized Turnaround Rate."
                    elif s_val_raw < 0 and e_val_raw < 0 and abs(e_val_raw) < abs(s_val_raw) and years_span > 0:
                        calc_cagr = (((abs(s_val_raw) - abs(e_val_raw)) / abs(s_val_raw)) / years_span) * 100.0
                        cagr_str = f"{calc_cagr:+.2f}%"
                        note_msg = "ℹ️ Loss reduction detected (losses shrank over time). Displaying Annualized Loss Reduction Rate."
                    else:
                        cagr_str = "N/A"

                    if s_val_raw != 0:
                        tot_growth_val = (((e_val_raw - s_val_raw) / abs(s_val_raw)) * 100.0)
                        tot_growth_str = f"{tot_growth_val:+.2f}%"
                    else:
                        tot_growth_str = "N/A"

                    m_card1, m_card2, m_card3, m_card4 = st.columns(4)
                    with m_card1:
                        st.metric(f"Start Value ({start_p})", f"{s_val_disp:,.2f} {unit_label_str}")
                    with m_card2:
                        st.metric(f"End Value ({end_p})", f"{e_val_disp:,.2f} {unit_label_str}")
                    with m_card3:
                        st.metric("Total Period Growth", tot_growth_str)
                    with m_card4:
                        st.metric(f"Compound Growth (CAGR)", cagr_str)

                    if note_msg:
                        st.caption(note_msg)



                    # Trend Chart for Selected Metric
                    df_analyzer_slice = pd.DataFrame(analyzer_records[start_idx : end_idx + 1])
                    df_analyzer_slice["metric_val_disp"] = df_analyzer_slice[selected_metric_key].apply(lambda v: round(float(v or 0.0) * val_factor, 2))
                    df_analyzer_slice["pct_change_%"] = (df_analyzer_slice["metric_val_disp"].pct_change() * 100.0).round(2)

                    fig_an = px.bar(
                        df_analyzer_slice,
                        x="period_label",
                        y="metric_val_disp",
                        title=f"{selected_metric_name} Trend ({start_p} to {end_p}) in {unit_label_str}",
                        labels={"metric_val_disp": f"{selected_metric_name} ({unit_label_str})", "period_label": "Period"},
                        text_auto=".2f",
                    )
                    st.plotly_chart(fig_an, use_container_width=True)

                    st.markdown(f"**Period Breakdown Table for {selected_metric_name}:**")
                    display_slice_cols = [c for c in ["period_label", "metric_val_disp", "pct_change_%"] if c in df_analyzer_slice.columns]
                    st.dataframe(
                        df_analyzer_slice[display_slice_cols].rename(
                            columns={"metric_val_disp": f"{selected_metric_name} ({unit_label_str})", "pct_change_%": "Period Growth %"}
                        ),
                        use_container_width=True,
                    )
            else:
                st.info(f"Add at least 2 {selected_period_type.lower()} records to use the CAGR & Growth Analyzer.")


        with st.expander("📝 Add / Update Financial Record"):
            with st.form("financial_form"):
                p_type_input = st.radio("Period Type", ["Annual", "Quarterly"], horizontal=True)
                col_period1, col_period2 = st.columns(2)
                with col_period1:
                    fy = st.number_input("Fiscal Year", min_value=2000, max_value=2030, value=2025, step=1)
                with col_period2:
                    fq = 1
                    if p_type_input == "Quarterly":
                        fq = st.selectbox("Fiscal Quarter", [1, 2, 3, 4], format_func=lambda q: f"Q{q} (Quarter {q})")

                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    rev = st.number_input("Revenue ($M)", value=0.0, step=100.0)
                    gp = st.number_input("Gross Profit ($M)", value=0.0, step=100.0)
                    op_inc = st.number_input("Operating Income ($M)", value=0.0, step=100.0)
                    net_inc = st.number_input("Net Income ($M)", value=0.0, step=100.0)
                with f_col2:
                    eps_val = st.number_input("EPS ($)", value=0.0, step=0.1)
                    ocf_val = st.number_input("Operating Cash Flow ($M)", value=0.0, step=100.0)
                    fcf_val = st.number_input("Free Cash Flow ($M)", value=0.0, step=100.0)
                    capex_val = st.number_input("CaPex ($M)", value=0.0, step=50.0)
                with f_col3:
                    rnd_val = st.number_input("R&D ($M)", value=0.0, step=50.0)
                    sbc_val = st.number_input("SBC ($M)", value=0.0, step=10.0)
                    cash_val = st.number_input("Cash & Equiv ($M)", value=0.0, step=500.0)
                    debt_val = st.number_input("Total Debt ($M)", value=0.0, step=500.0)
                    shares_val = st.number_input("Shares Outstanding (M)", value=1.0, step=1.0)

                fin_submitted = st.form_submit_button("Save Financial Record")
                if fin_submitted:
                    financial_repository.create_or_update(
                        selected_cid,
                        int(fy),
                        {
                            "period_type": p_type_input,
                            "fiscal_quarter": fq if p_type_input == "Quarterly" else None,
                            "revenue": rev,
                            "gross_profit": gp,
                            "operating_income": op_inc,
                            "net_income": net_inc,
                            "eps": eps_val,
                            "operating_cash_flow": ocf_val,
                            "free_cash_flow": fcf_val,
                            "capex": capex_val,
                            "rnd": rnd_val,
                            "sbc": sbc_val,
                            "cash": cash_val,
                            "debt": debt_val,
                            "shares_outstanding": shares_val,
                        },
                        period_type=p_type_input,
                        fiscal_quarter=fq if p_type_input == "Quarterly" else None,
                    )
                    label_str = f"{fy} Q{fq}" if p_type_input == "Quarterly" else f"FY{fy}"
                    st.success(f"Saved {label_str} financials for company!")
                    st.rerun()

else:
    st.info("No companies match the current search.")
