import streamlit as st

from services.scoring import validate_probability_mix
from services.valuation import calculate_expected_return, calculate_future_fcf, calculate_future_revenue

st.title("Valuation")
st.caption("Bear, Base, and Bull scenarios with probability checks and expected return")

current_revenue = st.number_input("Current revenue", value=100.0, step=1.0)
current_share_price = st.number_input("Current share price", value=100.0, step=1.0)

scenarios = {
    "Bear": {"probability": 25, "cagr": -0.05, "years": 5, "fcf_margin": 0.08, "terminal_multiple": 10},
    "Base": {"probability": 50, "cagr": 0.10, "years": 5, "fcf_margin": 0.12, "terminal_multiple": 12},
    "Bull": {"probability": 25, "cagr": 0.18, "years": 5, "fcf_margin": 0.15, "terminal_multiple": 15},
}

for name, values in scenarios.items():
    with st.expander(f"{name} scenario", expanded=(name == "Base")):
        values["probability"] = st.number_input(f"{name} probability", min_value=0, max_value=100, value=values["probability"])
        values["cagr"] = st.number_input(f"{name} CAGR", value=values["cagr"], format="%.4f")
        values["years"] = st.number_input(f"{name} forecast years", min_value=1, max_value=15, value=values["years"], step=1)
        values["fcf_margin"] = st.number_input(f"{name} FCF margin", value=values["fcf_margin"], format="%.4f")
        values["terminal_multiple"] = st.number_input(f"{name} terminal multiple", value=values["terminal_multiple"], step=0.1)

probabilities = {key.lower(): values["probability"] for key, values in scenarios.items()}
if not validate_probability_mix(probabilities):
    st.error("Probability validation failed: Bear + Base + Bull must equal 100%.")
else:
    st.success("Probability mix is internally consistent.")

st.subheader("Scenario output")
for name, values in scenarios.items():
    future_revenue = calculate_future_revenue(current_revenue, values["cagr"], values["years"])
    future_fcf = calculate_future_fcf(future_revenue, values["fcf_margin"])
    future_share_price = future_fcf * values["terminal_multiple"]
    annual_return = calculate_expected_return(current_share_price, future_share_price, values["years"])
    st.metric(f"{name} implied share price", round(future_share_price, 2))
    st.caption(f"Future revenue: {future_revenue:,.2f} | Future FCF: {future_fcf:,.2f} | Expected return: {annual_return:.2%}")
