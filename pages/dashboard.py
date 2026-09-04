import pandas as pd
import plotly.express as px
import streamlit as st

from database.store import analysis_repository, company_repository, financial_repository, scenario_repository

st.title("Investment Dashboard")
st.caption("Portfolio overview, valuation targets, and conviction rankings")

companies = company_repository.list_all()
analyses = analysis_repository.list_all()

if companies:
    rows = []
    for company in companies:
        cid = company["id"]
        latest_analysis = analysis_repository.get_latest_for_company(cid)
        latest_fin = financial_repository.get_latest(cid)

        val_target = "N/A"
        if latest_analysis:
            aid = latest_analysis["id"]
            if latest_fin:
                val_res = scenario_repository.calculate_scenario_outputs(
                    aid,
                    current_revenue=float(latest_fin["revenue"]),
                    current_share_price=100.0,
                    cash=float(latest_fin["cash"]),
                    debt=float(latest_fin["debt"]),
                    shares_outstanding=float(latest_fin["shares_outstanding"]),
                )
                if val_res["weighted_implied_share_price"] > 0:
                    val_target = f"${val_res['weighted_implied_share_price']:,.2f}"

        rows.append({
            "Ticker": company["ticker"],
            "Company": company["name"],
            "Status": company.get("status", "Watchlist"),
            "Sector": company.get("sector", "N/A"),
            "Decision": latest_analysis.get("decision", "Watch") if latest_analysis else "Not Analyzed",
            "Quality Score": latest_analysis.get("overall_score", 0.0) if latest_analysis else 0.0,
            "Confidence": f"{latest_analysis.get('confidence', 0)}%" if latest_analysis else "0%",
            "Latest Revenue ($M)": float(latest_fin["revenue"]) if latest_fin else "N/A",
            "Weighted Valuation Target": val_target,
            "Last Analysis Date": latest_analysis.get("analysis_date", "N/A") if latest_analysis else "N/A",
        })

    df_dashboard = pd.DataFrame(rows)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Tracked Companies", len(companies))
    with m2:
        buy_count = sum(1 for r in rows if r["Decision"] in ["Buy", "Strong Buy"])
        st.metric("Buy / Strong Buy", buy_count)
    with m3:
        avg_score = df_dashboard["Quality Score"].mean() if not df_dashboard.empty else 0.0
        st.metric("Avg Quality Score", f"{avg_score:.2f} / 10")
    with m4:
        watchlist_count = sum(1 for r in rows if r["Status"] == "Watchlist")
        st.metric("Watchlist Names", watchlist_count)

    st.subheader("Overview & Rankings")
    st.dataframe(df_dashboard, use_container_width=True)

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        if not df_dashboard.empty:
            fig_dec = px.pie(
                df_dashboard,
                names="Decision",
                title="Investment Decisions Breakdown",
                hole=0.4,
            )
            st.plotly_chart(fig_dec, use_container_width=True)
    with col_chart2:
        if not df_dashboard.empty:
            fig_score = px.bar(
                df_dashboard,
                x="Ticker",
                y="Quality Score",
                color="Decision",
                title="Company Quality Score Ranking",
            )
            st.plotly_chart(fig_score, use_container_width=True)
else:
    st.info("No companies available yet. Add a company to begin building your investment research platform.")
