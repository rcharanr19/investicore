from __future__ import annotations

import streamlit as st

from services.framework import load_framework

st.title("Research Framework")
st.caption("Structured fundamental review organized by business, industry, moat, and thesis")

framework = load_framework()
answers = st.session_state.setdefault("research_answers", {})

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
                new_value = st.slider(label, min_value=scale[0], max_value=scale[1], value=int(value) if value is not None else scale[0])
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
                new_value = st.selectbox(label, options, index=options.index(value) if value in options else 0)
            else:
                new_value = st.text_input(label, value=value or "")

            answers[qid] = new_value

if st.button("Save answers to session"):
    st.success("Research answers are saved in the session state for this run.")
    st.json(answers)
