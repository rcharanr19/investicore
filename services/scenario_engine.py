from __future__ import annotations

from typing import Any

from services.valuation import calculate_expected_return, calculate_future_fcf, calculate_future_revenue


def generate_sensitivity_matrix(
    current_revenue: float,
    current_share_price: float,
    cagr: float,
    years: int,
    fcf_margins: list[float],
    terminal_multiples: list[float],
    cash: float = 0.0,
    debt: float = 0.0,
    shares_outstanding: float = 1.0,
) -> dict[str, Any]:
    """Generates a 2D matrix of implied share prices and CAGR returns varying FCF margin vs Terminal multiple."""
    shares = max(shares_outstanding, 1.0)
    cagr_decimal = cagr / 100.0 if cagr > 1.0 else cagr

    price_matrix = []
    return_matrix = []

    future_rev = calculate_future_revenue(current_revenue, cagr_decimal, years)

    for margin in fcf_margins:
        price_row = []
        return_row = []
        future_fcf = calculate_future_fcf(future_rev, margin)
        for mult in terminal_multiples:
            equity_val = (future_fcf * mult) + cash - debt
            implied_price = equity_val / shares
            annual_return = calculate_expected_return(current_share_price, max(implied_price, 0.01), years)

            price_row.append(round(implied_price, 2))
            return_row.append(round(annual_return * 100.0, 2))

        price_matrix.append(price_row)
        return_matrix.append(return_row)

    return {
        "fcf_margins": [round(m * 100, 1) for m in fcf_margins],
        "terminal_multiples": terminal_multiples,
        "implied_price_matrix": price_matrix,
        "return_matrix": return_matrix,
        "future_revenue": round(future_rev, 2),
    }


def calculate_risk_adjusted_valuation(
    weighted_implied_price: float,
    risk_score: float,  # 1 to 10 scale (10 is low risk)
    thesis_breakers_triggered: bool = False,
    hurdle_rate: float = 0.15,  # 15% required CAGR return
) -> dict[str, Any]:
    """Calculates risk-adjusted fair value and maximum recommended buy price based on risk score and thesis breakers."""
    # Base margin of safety requirement = 15% to 40% based on risk score
    # Lower quality/risk score (e.g. 4/10) requires higher margin of safety (e.g. 35%)
    base_mos_pct = max(0.15, min(0.45, 0.50 - (risk_score * 0.035)))

    if thesis_breakers_triggered:
        # Increase margin of safety by 15% penalty if thesis breakers are triggered
        base_mos_pct = min(0.60, base_mos_pct + 0.15)

    max_buy_price = weighted_implied_price * (1.0 - base_mos_pct)

    return {
        "raw_implied_price": round(weighted_implied_price, 2),
        "required_margin_of_safety_pct": round(base_mos_pct * 100, 1),
        "max_recommended_buy_price": round(max_buy_price, 2),
        "risk_score": risk_score,
        "thesis_breakers_triggered": thesis_breakers_triggered,
        "hurdle_rate_pct": round(hurdle_rate * 100, 1),
    }
