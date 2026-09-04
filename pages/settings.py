import os
import streamlit as st

from database.client import get_db_table, get_supabase_client

st.title("Settings & Diagnostics")
st.caption("Application configuration, database connection diagnostics, and environment status")

st.subheader("🔌 Database Connection Status")

client = get_supabase_client()
if client is not None:
    st.success("✅ Supabase Client Connected Successfully!")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        comp_table = get_db_table("companies")
        if comp_table:
            try:
                res = comp_table.select("*").execute()
                st.metric("Companies in DB", len(res.data) if res.data else 0)
            except Exception as e:
                st.error(f"Error querying companies: {e}")
    with col2:
        an_table = get_db_table("analyses")
        if an_table:
            try:
                res_a = an_table.select("*").execute()
                st.metric("Analyses in DB", len(res_a.data) if res_a.data else 0)
            except Exception as e:
                st.error(f"Error querying analyses: {e}")
    with col3:
        fin_table = get_db_table("financials")
        if fin_table:
            try:
                res_f = fin_table.select("*").execute()
                st.metric("Financial Statements in DB", len(res_f.data) if res_f.data else 0)
            except Exception as e:
                st.error(f"Error querying financials: {e}")
else:
    st.warning("⚠️ Running in Local In-Memory Fallback Mode (Supabase client not connected).")
    st.info("To enable live cloud storage, ensure `SUPABASE_URL` and `SUPABASE_KEY` are placed at the **TOP** of your Streamlit secrets before any TOML `[section]` headers.")

st.divider()
st.subheader("⚙️ Streamlit Secrets TOML Formatting Tip")
st.markdown("""
In TOML files (like Streamlit **Settings $\rightarrow$ Secrets**), section headers (like `[connections.postgresql]`) capture **all** key-value pairs listed below them.

To ensure both Streamlit SQL connection and Supabase client work correctly, place `SUPABASE_URL` and `SUPABASE_KEY` at the **very top**:

```toml
# Place top-level keys at the top BEFORE any [sections]
SUPABASE_URL = "https://yztyqyyldnxqnvnetvig.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1..."
APP_ENV = "development"

# Database connection section
[connections.postgresql]
type = "sql"
dialect = "postgresql"
driver = "psycopg"
host = "aws-1-us-east-1.pooler.supabase.com"
port = 5432
database = "postgres"
username = "postgres.yztyqyyldnxqnvnetvig"
password = "..."
sslmode = "require"
```
""")

