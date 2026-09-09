from services.valuation import calculate_future_revenue, calculate_future_fcf, calculate_expected_return, calculate_valuation


def test_valuation_calculations():
    future_rev = calculate_future_revenue(current_revenue=100, cagr=0.15, years=5)
    assert round(future_rev, 2) == 201.14

    future_fcf = calculate_future_fcf(future_revenue=future_rev, fcf_margin=0.12)
    assert round(future_fcf, 2) == 24.14

    valuation = calculate_valuation(
        current_revenue=100,
        cagr=0.15,
        years=5,
        terminal_revenue=250,
        operating_margin=0.15,
        fcf_margin=0.12,
        terminal_multiple=12,
        cash=20,
        debt=10,
        current_share_price=100,
    )

    assert valuation["future_revenue"] > 0
    assert valuation["future_fcf"] > 0
    assert valuation["equity_value"] > 0
    assert valuation["implied_share_price"] > 0


def test_expected_return():
    result = calculate_expected_return(current_share_price=100, future_share_price=150, years=5)
    assert round(result, 4) == 0.0845


def test_return_decomposition_and_expected_cagr():
    from services.valuation import calculate_expected_cagr_pct, calculate_return_decomposition

    cagr_pct = calculate_expected_cagr_pct(current_value=100, future_value=150, years=5)
    assert round(cagr_pct, 2) == 8.45

    decomposition = calculate_return_decomposition(
        expected_cagr_pct=22.0,
        growth_contribution_pct=15.0,
        capital_returns_pct=2.0,
        multiple_expansion_pct=5.0,
    )

    assert decomposition["expected_cagr_pct"] == 22.0
    assert decomposition["total_contribution_pct"] == 22.0
    assert decomposition["reconciliation_gap_pct"] == 0.0
    assert decomposition["components"]["growth_contribution_pct"] == 15.0
    assert decomposition["components"]["capital_returns_pct"] == 2.0
    assert decomposition["components"]["multiple_expansion_pct"] == 5.0
