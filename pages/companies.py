import streamlit as st

from database.store import add_company, company_repository

st.title("Company Records")
st.caption("Add, search, and track the companies you are researching")

with st.form("company_form"):
    col1, col2 = st.columns(2)
    with col1:
        ticker = st.text_input("Ticker")
        name = st.text_input("Company name")
        sector = st.text_input("Sector")
        industry = st.text_input("Industry")
    with col2:
        country = st.text_input("Country")
        website = st.text_input("Website")
        status = st.selectbox("Status", ["Researching", "Watchlist", "Owned", "Buy Candidate", "Avoid", "Sold", "Archived"])
        description = st.text_area("Description")
    submitted = st.form_submit_button("Save company")
    if submitted:
        if not ticker or not name:
            st.warning("Ticker and company name are required.")
        else:
            add_company(
                {
                    "ticker": ticker.upper(),
                    "name": name,
                    "sector": sector,
                    "industry": industry,
                    "country": country,
                    "website": website,
                    "status": status,
                    "description": description,
                }
            )
            st.success(f"Saved {name} ({ticker.upper()}).")

search = st.text_input("Search companies")
company_rows = company_repository.search(search) if search else company_repository.list_all()
if company_rows:
    st.dataframe(company_rows, use_container_width=True)
else:
    st.info("No companies match the current search.")
