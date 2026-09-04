from __future__ import annotations

import streamlit as st

from database.client import ensure_database
from database.store import seed_core_data

st.set_page_config(page_title="Investment Research Platform", page_icon="📈", layout="wide")

ensure_database()
seed_core_data()

pages = [
    st.Page("pages/dashboard.py", title="Dashboard", icon="📊"),
    st.Page("pages/companies.py", title="Companies", icon="🏢"),
    st.Page("pages/new_analysis.py", title="New Analysis", icon="📝"),
    st.Page("pages/research.py", title="Research", icon="🔎"),
    st.Page("pages/valuation.py", title="Valuation", icon="💰"),
    st.Page("pages/thesis_journal.py", title="Thesis Journal", icon="📒"),
    st.Page("pages/settings.py", title="Settings", icon="⚙️"),
]

nav = st.navigation(pages)
nav.run()
