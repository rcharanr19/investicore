import streamlit as st

from database.store import analysis_repository, company_repository

st.title("Thesis Journal")
st.caption("Track historical versions and compare changes in assumptions, scores, valuation, thesis, and risk")

companies = company_repository.list_all()
if not companies:
    st.info("Create a company before building a thesis journal.")
    st.stop()

company_id = st.selectbox(
    "Company",
    [company["id"] for company in companies],
    format_func=lambda cid: next((f"{company['ticker']} - {company['name']}" for company in companies if company["id"] == cid), "Select company"),
)
versions = analysis_repository.get_versions_for_company(company_id)
if not versions:
    st.info("No versions for the selected company yet.")
    st.stop()

version_labels = [f"v{item.get('version_number', 1)} - {item.get('analysis_date', 'Unknown')}" for item in versions]
selected = st.selectbox("Version to inspect", version_labels)
record = versions[version_labels.index(selected)]
st.write(record)

if len(versions) > 1:
    choose_previous = st.selectbox(
        "Compare against earlier version",
        version_labels[:-1],
        index=max(len(version_labels) - 2, 0),
    )
    previous = versions[version_labels.index(choose_previous)]
    current = record
    st.subheader("Version comparison")
    comparison = analysis_repository.compare_versions(previous["id"], current["id"])
    st.json({
        "Previous version": f"v{previous.get('version_number', 1)} - {previous.get('analysis_date', 'Unknown')}",
        "Current version": f"v{current.get('version_number', 1)} - {current.get('analysis_date', 'Unknown')}",
        "Decision change": comparison.get("decision_change"),
        "Score change": comparison.get("score_change"),
        "Notes change": comparison.get("notes_change"),
        "Change summary": current.get("change_summary", ""),
        "Answers stored": analysis_repository.get_answers(current["id"]),
    })
