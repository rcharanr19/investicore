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
