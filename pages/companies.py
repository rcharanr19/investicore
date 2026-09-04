import pandas as pd
import plotly.express as px
import streamlit as st

from database.store import add_company, company_repository, financial_repository

st.title("Company Records")
st.caption("Add, search, and track the companies you are researching")

with st.expander("➕ Add New Company", expanded=False):
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
        fin_records = financial_repository.get_by_company(selected_cid)
        if fin_records:
            df_fin = pd.DataFrame(fin_records)
            display_cols = [c for c in ["fiscal_year", "revenue", "gross_profit", "operating_income", "net_income", "eps", "free_cash_flow", "capex", "cash", "debt"] if c in df_fin.columns]
            st.write("Historical Financial Statements ($ in Millions):")
            st.dataframe(df_fin[display_cols], use_container_width=True)

            cagr = financial_repository.calculate_historical_cagr(selected_cid, "revenue")
            if cagr is not None:
                st.info(f"Historical Revenue CAGR: **{cagr:.2f}%** across {len(fin_records)} recorded fiscal years.")

            fig = px.bar(
                df_fin,
                x="fiscal_year",
                y=["revenue", "net_income", "free_cash_flow"],
                barmode="group",
                title="Revenue, Net Income & Free Cash Flow Trend",
                labels={"value": "Amount ($M)", "fiscal_year": "Fiscal Year", "variable": "Metric"},
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No financial statement records entered for this company yet.")

        with st.expander("📝 Add / Update Financial Year Record"):
            with st.form("financial_form"):
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    fy = st.number_input("Fiscal Year", min_value=2000, max_value=2030, value=2025, step=1)
                    rev = st.number_input("Revenue ($M)", value=0.0, step=100.0)
                    gp = st.number_input("Gross Profit ($M)", value=0.0, step=100.0)
                    op_inc = st.number_input("Operating Income ($M)", value=0.0, step=100.0)
                with f_col2:
                    net_inc = st.number_input("Net Income ($M)", value=0.0, step=100.0)
                    eps_val = st.number_input("EPS ($)", value=0.0, step=0.1)
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
                    financial_repository.create_or_update(selected_cid, int(fy), {
                        "revenue": rev,
                        "gross_profit": gp,
                        "operating_income": op_inc,
                        "net_income": net_inc,
                        "eps": eps_val,
                        "free_cash_flow": fcf_val,
                        "capex": capex_val,
                        "rnd": rnd_val,
                        "sbc": sbc_val,
                        "cash": cash_val,
                        "debt": debt_val,
                        "shares_outstanding": shares_val,
                    })
                    st.success(f"Saved FY{fy} financials for company!")
                    st.rerun()
else:
    st.info("No companies match the current search.")
