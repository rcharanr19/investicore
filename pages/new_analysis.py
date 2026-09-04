import streamlit as st

from database.store import analysis_repository, company_repository

st.title("New Analysis")
st.caption("Create a new analysis or a versioned update to an existing thesis")

companies = company_repository.list_all()
company_names = {company["id"]: f"{company['ticker']} - {company['name']}" for company in companies}
company_id = st.selectbox("Company", list(company_names.keys()), format_func=lambda cid: company_names.get(cid, "Select company"))
copy_previous = st.radio("Copy previous analysis?", ["No", "Yes"], index=0)

if company_id:
    previous = analysis_repository.get_latest_for_company(company_id)
    if previous and copy_previous == "Yes":
        st.info(f"Previous version detected: v{previous.get('version_number', 1)} — {previous.get('analysis_date', 'Unknown')}")

    with st.form("analysis_form"):
        analysis_date = st.date_input("Analysis date")
        status = st.selectbox("Status", ["Draft", "Completed", "Archived"])
        decision = st.selectbox("Decision", ["Strong Buy", "Buy", "Watch", "Hold", "Avoid", "Sell"])
        confidence = st.slider("Confidence", 0, 100, 70)
        overall_score = st.slider("Overall quality score", 0.0, 10.0, 7.5, step=0.1)
        notes = st.text_area("Notes", value="Training / Sample Analysis" if previous is None else previous.get("notes", ""))
        change_summary = st.text_area("Change summary")

        submitted = st.form_submit_button("Create analysis")
        if submitted:
            version_number = 1 if previous is None else (previous.get("version_number", 1) + 1)
            record = {
                "company_id": company_id,
                "framework_version": "1.0",
                "analysis_date": str(analysis_date),
                "status": status,
                "decision": decision,
                "confidence": confidence,
                "overall_score": float(overall_score),
                "notes": notes,
                "version_number": version_number,
                "previous_analysis_id": previous["id"] if previous and copy_previous == "Yes" else None,
                "change_summary": change_summary or ("Copied previous analysis" if previous and copy_previous == "Yes" else "Initial analysis"),
            }
            created = analysis_repository.create(record)
            st.success(f"Created new analysis version v{version_number} for {company_names[company_id]}.")
            st.json(created)
else:
    st.warning("Create or select a company before starting a research analysis.")
