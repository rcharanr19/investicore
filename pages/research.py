from __future__ import annotations

import streamlit as st

from database.store import analysis_repository, company_repository
from services.framework import load_framework

st.title("Research Framework")
st.caption("Structured fundamental review organized by business, industry, moat, and thesis")

companies = company_repository.list_all()
if not companies:
    st.warning("Create a company first so you can attach research answers to a valid analysis.")
    st.stop()

company_id = st.selectbox(
    "Company",
    [company["id"] for company in companies],
    format_func=lambda cid: next((f"{company['ticker']} - {company['name']}" for company in companies if company["id"] == cid), "Select company"),
)

versions = analysis_repository.get_versions_for_company(company_id)
if not versions:
    st.info("No analyses exist for this company yet. Create one from the New Analysis page to begin research.")
    st.stop()

analysis_id = st.selectbox(
    "Analysis version",
    [analysis["id"] for analysis in versions],
    format_func=lambda aid: next(
        (f"v{analysis.get('version_number', 1)} - {analysis.get('analysis_date', 'Unknown')}" for analysis in versions if analysis["id"] == aid),
        "Select analysis",
    ),
)
analysis = analysis_repository.get_by_id(analysis_id)
framework = load_framework()
answers_bucket = st.session_state.setdefault("research_answers", {})
analysis_key = f"analysis_{analysis_id}"
if analysis_key not in answers_bucket:
    answers_bucket[analysis_key] = analysis_repository.get_answers(analysis_id)
answers = answers_bucket[analysis_key]

st.subheader(f"{analysis.get('decision', 'Watch')} | Score {analysis.get('overall_score', 0)} | v{analysis.get('version_number', 1)}")

for section in framework.get("sections", []):
    with st.expander(section["name"], expanded=True):
        for question in section.get("questions", []):
            qid = question["id"]
            qtype = question["type"]
            label = question["question"]
            value = answers.get(qid)

            if qtype == "short_text":
                new_value = st.text_input(label, value=value or "")
            elif qtype == "long_text":
                new_value = st.text_area(label, value=value or "")
            elif qtype == "score":
                scale = question.get("score_scale", [1, 10])
                default = int(value) if value is not None else scale[0]
                new_value = st.slider(label, min_value=scale[0], max_value=scale[1], value=default)
            elif qtype == "percentage":
                new_value = st.number_input(label, value=float(value) if value is not None else 0.0, min_value=0.0, max_value=1000.0, step=0.1)
            elif qtype == "number":
                new_value = st.number_input(label, value=float(value) if value is not None else 0.0, step=0.1)
            elif qtype == "currency":
                new_value = st.number_input(label, value=float(value) if value is not None else 0.0, step=1000000.0)
            elif qtype == "date":
                new_value = st.date_input(label, value=value if value is not None else None)
            elif qtype == "select":
                options = question.get("options", [])
                index = options.index(value) if value in options else 0
                new_value = st.selectbox(label, options, index=index)
            else:
                new_value = st.text_input(label, value=value or "")

            answers[qid] = new_value

if st.button("Save answers to analysis"):
    analysis_repository.save_answers(analysis_id, answers)
    st.success(f"Saved {len(answers)} responses for analysis v{analysis.get('version_number', 1)}.")
    st.json(analysis_repository.get_answers(analysis_id))
