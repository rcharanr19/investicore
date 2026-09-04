import pandas as pd
import plotly.express as px
import streamlit as st

from database.store import analysis_repository, company_repository, financial_repository, scenario_repository
from services.scoring import validate_probability_mix

st.title("Valuation & Scenario Modeling")
st.caption("Bear, Base, and Bull scenario forecasting with probability weighting and expected return targets")

companies = company_repository.list_all()
if not companies:
    st.warning("Please create a company record first.")
    st.stop()

selected_cid = st.selectbox(
    "Company",
    [c["id"] for c in companies],
    format_func=lambda cid: next(f"{c['ticker']} - {c['name']}" for c in companies if c["id"] == cid),
)

versions = analysis_repository.get_versions_for_company(selected_cid)
if not versions:
    st.info("No research analyses found for this company. Create one under New Analysis to link valuation scenarios.")
    st.stop()

selected_aid = st.selectbox(
    "Analysis version",
    [a["id"] for a in versions],
    format_func=lambda aid: next(f"v{a.get('version_number', 1)} - {a.get('analysis_date', 'Unknown')}" for a in versions if a["id"] == aid),
)

# Load baseline financial metrics if available
latest_fin = financial_repository.get_latest(selected_cid)
default_rev = float(latest_fin["revenue"]) if latest_fin else 1000.0
default_cash = float(latest_fin["cash"]) if latest_fin else 0.0
default_debt = float(latest_fin["debt"]) if latest_fin else 0.0
default_shares = float(latest_fin["shares_outstanding"]) if latest_fin else 50.0

st.subheader("Baseline Inputs")
b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5)
with b_col1:
    current_revenue = st.number_input("Current Revenue ($M)", value=default_rev, step=100.0)
with b_col2:
    current_share_price = st.number_input("Current Share Price ($)", value=100.0, step=1.0)
with b_col3:
    cash = st.number_input("Cash & Equiv ($M)", value=default_cash, step=50.0)
with b_col4:
    debt = st.number_input("Total Debt ($M)", value=default_debt, step=50.0)
with b_col5:
    shares_outstanding = st.number_input("Shares Outstanding (M)", value=max(default_shares, 1.0), step=1.0)

# Load saved scenarios or defaults
saved_scenarios = scenario_repository.get_scenarios(selected_aid)
defaults = {
    "Bear": {"probability": 25, "revenue_cagr": 0.05, "forecast_period": 5, "fcf_margin": 0.20, "terminal_multiple": 12.0},
    "Base": {"probability": 50, "revenue_cagr": 0.12, "forecast_period": 5, "fcf_margin": 0.28, "terminal_multiple": 16.0},
    "Bull": {"probability": 25, "revenue_cagr": 0.18, "forecast_period": 5, "fcf_margin": 0.35, "terminal_multiple": 20.0},
}
active_scenarios = saved_scenarios if saved_scenarios else defaults

st.subheader("Scenario Parameters")
scenarios_input = {}
cols = st.columns(3)

for idx, (name, values) in enumerate(active_scenarios.items()):
    with cols[idx % 3]:
        st.markdown(f"### {name} Scenario")
        prob = st.number_input(f"{name} Probability (%)", min_value=0, max_value=100, value=int(values.get("probability", 33)), key=f"prob_{name}")
        cagr = st.number_input(f"{name} Revenue CAGR (decimal, e.g. 0.12 = 12%)", value=float(values.get("revenue_cagr", 0.10)), format="%.4f", key=f"cagr_{name}")
        years = st.number_input(f"{name} Forecast Years", min_value=1, max_value=15, value=int(values.get("forecast_period", 5)), step=1, key=f"years_{name}")
        fcf_m = st.number_input(f"{name} FCF Margin (decimal)", value=float(values.get("fcf_margin", 0.20)), format="%.4f", key=f"fcf_{name}")
        mult = st.number_input(f"{name} Terminal FCF Multiple", value=float(values.get("terminal_multiple", 15.0)), step=0.5, key=f"mult_{name}")

        scenarios_input[name] = {
            "probability": prob,
            "revenue_cagr": cagr,
            "forecast_period": years,
            "fcf_margin": fcf_m,
            "terminal_multiple": mult,
        }

probabilities = {name.lower(): vals["probability"] for name, vals in scenarios_input.items()}
if not validate_probability_mix(probabilities):
    st.error("⚠️ Probability validation failed: Bear + Base + Bull probabilities must sum to 100%.")
else:
    st.success("✅ Probability distribution validated (100% total).")

    if st.button("💾 Save Valuation Scenarios"):
        scenario_repository.save_scenarios(selected_aid, scenarios_input)
        st.success("Saved scenario configuration to analysis!")

    # Perform valuation outputs calculation
    # First temporarily store in repo for calculation consistency
    scenario_repository.save_scenarios(selected_aid, scenarios_input)
    val_result = scenario_repository.calculate_scenario_outputs(
        selected_aid,
        current_revenue=current_revenue,
        current_share_price=current_share_price,
        cash=cash,
        debt=debt,
        shares_outstanding=shares_outstanding,
    )

    st.divider()
    st.subheader("📈 Valuation Outputs & Target Share Prices")

    res_scen = val_result["scenarios"]
    w_price = val_result["weighted_implied_share_price"]
    w_return = val_result["weighted_expected_return"]

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Weighted Target Share Price", f"${w_price:,.2f}")
    with m2:
        st.metric("Weighted Expected Annual Return (CAGR)", f"{w_return:.2%}")
    with m3:
        upside = ((w_price / current_share_price) - 1.0) if current_share_price > 0 else 0.0
        st.metric("Implied Upside / Margin of Safety", f"{upside:+.2%}")

    chart_data = []
    for s_name, s_res in res_scen.items():
        chart_data.append({
            "Scenario": s_name,
            "Implied Price ($)": round(s_res["implied_share_price"], 2),
            "Expected Annual Return": f"{s_res['expected_annual_return']:.2%}",
            "Future Revenue ($M)": round(s_res["future_revenue"], 2),
            "Future FCF ($M)": round(s_res["future_fcf"], 2),
        })

    chart_data.append({
        "Scenario": "Weighted Average",
        "Implied Price ($)": round(w_price, 2),
        "Expected Annual Return": f"{w_return:.2%}",
        "Future Revenue ($M)": "-",
        "Future FCF ($M)": "-",
    })
    chart_data.append({
        "Scenario": "Current Price",
        "Implied Price ($)": round(current_share_price, 2),
        "Expected Annual Return": "0.00%",
        "Future Revenue ($M)": "-",
        "Future FCF ($M)": "-",
    })

    df_out = pd.DataFrame(chart_data)
    st.table(df_out)

    fig = px.bar(
        df_out,
        x="Scenario",
        y="Implied Price ($)",
        color="Scenario",
        title="Share Price Comparison: Market Price vs. Scenarios & Weighted Fair Value",
        text_auto=".2f",
    )
    st.plotly_chart(fig, use_container_width=True)

