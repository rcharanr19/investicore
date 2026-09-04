import pandas as pd
import plotly.express as px
import streamlit as st

from database.store import (
    analysis_repository,
    company_repository,
    financial_repository,
    growth_driver_repository,
    risk_repository,
    scenario_repository,
    thesis_breaker_repository,
)
from services.scenario_engine import calculate_risk_adjusted_valuation, generate_sensitivity_matrix
from services.scoring import validate_probability_mix

st.title("Valuation & Scenario Modeling Engine")
st.caption("Bear, Base, Bull forecasting, 2D sensitivity matrix, risk-adjusted margin of safety, and thesis breaker monitoring")

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

# Load baseline financial metrics if available (TTM or latest Annual)
latest_fin = financial_repository.calculate_ttm(selected_cid) or financial_repository.get_latest(selected_cid)
default_rev = float(latest_fin["revenue"]) if latest_fin else 1000.0
default_cash = float(latest_fin["cash"]) if latest_fin else 0.0
default_debt = float(latest_fin["debt"]) if latest_fin else 0.0
default_shares = float(latest_fin["shares_outstanding"]) if latest_fin else 50.0

if latest_fin:
    st.info(f"Baseline Inputs loaded from: **{latest_fin.get('period_label', 'Latest Record')}**")

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
        try:
            scenario_repository.save_scenarios(selected_aid, scenarios_input)
            st.success("Saved scenario configuration to analysis!")
        except Exception as err:
            st.error(f"Error saving scenarios: {err}")

    # Calculate scenario outputs
    val_result = scenario_repository.calculate_scenario_outputs(
        selected_aid,
        current_revenue=current_revenue,
        current_share_price=current_share_price,
        cash=cash,
        debt=debt,
        shares_outstanding=shares_outstanding,
    )


    st.divider()
    st.subheader("📈 Scenario Valuation Outputs")

    res_scen = val_result["scenarios"]
    w_price = val_result["weighted_implied_share_price"]
    w_return = val_result["weighted_expected_return"]

    # Calculate Risk & Thesis Breaker Adjustment
    risk_score = risk_repository.calculate_aggregate_risk_score(selected_aid)
    breaker_status = thesis_breaker_repository.check_breakers_status(selected_aid)
    risk_adj = calculate_risk_adjusted_valuation(
        weighted_implied_price=w_price,
        risk_score=risk_score,
        thesis_breakers_triggered=breaker_status["has_triggered"],
    )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Weighted Target Share Price", f"${w_price:,.2f}")
    with m2:
        st.metric("Weighted Expected Annual Return", f"{w_return:.2%}")
    with m3:
        st.metric("Required Margin of Safety", f"{risk_adj['required_margin_of_safety_pct']:.1f}%")
    with m4:
        st.metric("Max Recommended Buy Price", f"${risk_adj['max_recommended_buy_price']:,.2f}")

    if breaker_status["has_triggered"]:
        st.error(f"🚨 ALERT: {breaker_status['triggered_count']} Thesis Breaker(s) Triggered! ({', '.join(breaker_status['triggered_conditions'])}) — Extra 15% Margin of Safety Applied.")

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
        "Scenario": "Weighted Fair Value",
        "Implied Price ($)": round(w_price, 2),
        "Expected Annual Return": f"{w_return:.2%}",
        "Future Revenue ($M)": "-",
        "Future FCF ($M)": "-",
    })
    chart_data.append({
        "Scenario": "Max Buy Price",
        "Implied Price ($)": round(risk_adj["max_recommended_buy_price"], 2),
        "Expected Annual Return": "-",
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
        title="Fair Value & Buy Price Target vs. Market Price",
        text_auto=".2f",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Valuation Sensitivity Matrix Section
    st.divider()
    st.subheader("📊 2D Valuation Sensitivity Matrix (Base Case)")
    st.caption("Implied target share price across varying FCF Margins and Terminal Multiples")

    base_params = active_scenarios.get("Base", {})
    base_cagr = float(base_params.get("revenue_cagr", 0.12))
    base_years = int(base_params.get("forecast_period", 5))

    margins_range = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    multiples_range = [10.0, 12.5, 15.0, 17.5, 20.0, 25.0]

    sens_data = generate_sensitivity_matrix(
        current_revenue=current_revenue,
        current_share_price=current_share_price,
        cagr=base_cagr,
        years=base_years,
        fcf_margins=margins_range,
        terminal_multiples=multiples_range,
        cash=cash,
        debt=debt,
        shares_outstanding=shares_outstanding,
    )

    df_sens = pd.DataFrame(
        sens_data["implied_price_matrix"],
        index=[f"FCF Margin {m}%" for m in sens_data["fcf_margins"]],
        columns=[f"{m}x Multiple" for m in sens_data["terminal_multiples"]],
    )
    st.dataframe(df_sens.style.background_gradient(cmap="Greens", axis=None), use_container_width=True)

    # Risk & Thesis Breakers Management Section
    st.divider()
    st.subheader("⚠️ Risk Register & Thesis Breakers Monitor")
    col_r1, col_r2 = st.columns(2)

    with col_r1:
        st.markdown("### Risk Register")
        risks = risk_repository.get_by_analysis(selected_aid)
        if risks:
            st.dataframe(pd.DataFrame(risks)[["category", "risk", "probability", "impact", "mitigation"]], use_container_width=True)
        else:
            st.info("No risks recorded for this analysis.")

        with st.expander("➕ Add Risk"):
            with st.form("add_risk_form"):
                r_desc = st.text_input("Risk Description")
                r_cat = st.selectbox("Category", ["Competition", "Regulation", "Technology", "Management", "Financial", "Macroeconomic", "Valuation", "Execution", "Other"])
                r_prob = st.slider("Probability (%)", 0, 100, 40)
                r_imp = st.slider("Impact (1-10)", 1, 10, 5)
                r_mit = st.text_input("Mitigation Strategy")
                if st.form_submit_button("Save Risk"):
                    risk_repository.create_or_update(selected_aid, {
                        "risk": r_desc,
                        "category": r_cat,
                        "probability": r_prob,
                        "impact": r_imp,
                        "mitigation": r_mit,
                    })
                    st.success("Added risk!")
                    st.rerun()

    with col_r2:
        st.markdown("### Thesis Breakers")
        breakers = thesis_breaker_repository.get_by_analysis(selected_aid)
        if breakers:
            st.dataframe(pd.DataFrame(breakers)[["condition", "metric", "threshold", "current_value", "current_status"]], use_container_width=True)
        else:
            st.info("No thesis breakers recorded for this analysis.")

        with st.expander("➕ Add Thesis Breaker"):
            with st.form("add_breaker_form"):
                b_cond = st.text_input("Breaker Condition (e.g. Revenue growth < 5%)")
                b_met = st.text_input("Metric Name")
                b_op = st.selectbox("Operator", ["<", "<=", ">", ">=", "=="])
                b_thresh = st.number_input("Threshold Value", value=0.0)
                b_curr = st.number_input("Current Value", value=0.0)
                if st.form_submit_button("Save Thesis Breaker"):
                    thesis_breaker_repository.create_or_update(selected_aid, {
                        "condition": b_cond,
                        "metric": b_met,
                        "operator": b_op,
                        "threshold": b_thresh,
                        "current_value": b_curr,
                    })
                    st.success("Added thesis breaker!")
                    st.rerun()


