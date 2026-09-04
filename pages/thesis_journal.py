import streamlit as st

from database.store import analysis_repository, company_repository

st.title("Thesis Journal")
st.caption("Track historical versions and compare changes in assumptions, scores, valuation, thesis, and risk")

company_id = st.selectbox(
    "Company",
    [company["id"] for company in company_repository.list_all()],
    format_func=lambda cid: next((c["ticker"] + " - " + c["name"] for c in company_repository.list_all() if c["id"] == cid), "Select company"),
)
versions = analysis_repository.get_versions_for_company(company_id)
if not versions:
    st.info("No versions for the selected company yet.")
else:
    selected = st.selectbox("Version to inspect", [f"v{item.get('version_number', 1)} - {item.get('analysis_date', 'Unknown')}" for item in versions])
    record = versions[[f"v{item.get('version_number', 1)} - {item.get('analysis_date', 'Unknown')}" for item in versions].index(selected)]
    st.write(record)

    if len(versions) > 1:
        previous = versions[-2]
        current = versions[-1]
        st.subheader("Version comparison")
        comparison = {
            "Changed assumptions": previous.get("change_summary", "") + " -> " + current.get("change_summary", ""),
            "Changed scores": f"Previous: {previous.get('overall_score', 0)} -> Current: {current.get('overall_score', 0)}",
            "Changed decision": f"Previous: {previous.get('decision', 'Watch')} -> Current: {current.get('decision', 'Watch')}",
            "Changed thesis": previous.get("notes", "") + " -> " + current.get("notes", ""),
        }
        st.json(comparison)
