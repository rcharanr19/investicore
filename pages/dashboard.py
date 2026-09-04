import streamlit as st

from database.store import analysis_repository, company_repository

st.title("Investment Dashboard")
st.caption("Portfolio overview for active research and watchlist names")

companies = company_repository.list_all()
analyses = analysis_repository.list_all()

if companies:
    rows = []
    for company in companies:
        latest = None
        for analysis in analyses:
            if analysis.get("company_id") == company["id"]:
                latest = max(analysis.get("version_number", 1) for analysis in analyses if analysis.get("company_id") == company["id"])
                latest_analysis = max(
                    [a for a in analyses if a.get("company_id") == company["id"]],
                    key=lambda item: item.get("version_number", 1),
                    default=None,
                )
                if latest_analysis:
                    rows.append(
                        {
                            "Company": company["name"],
                            "Ticker": company["ticker"],
                            "Decision": latest_analysis.get("decision", "Watch"),
                            "Overall Quality": latest_analysis.get("overall_score", 0),
                            "Confidence": latest_analysis.get("confidence", 0),
                            "Analysis Date": latest_analysis.get("analysis_date", "N/A"),
                        }
                    )
                break
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No analyses found yet. Create a company and a research note to populate the dashboard.")
else:
    st.info("No companies available yet.")
