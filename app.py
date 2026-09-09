from __future__ import annotations

import streamlit as st

from database.client import ensure_database

st.set_page_config(page_title="InvestiCore Phase 1", page_icon=":material/account_balance:", layout="wide")

ensure_database()

pages = [
    st.Page("pages/sec_data.py", title="SEC data", icon=":material/database:"),
]

nav = st.navigation(pages)
nav.run()
