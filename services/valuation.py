from __future__ import annotations


def calculate_cagr(start_value: float, end_value: float, years: int) -> float:
    if start_value <= 0 or years <= 0:
        raise ValueError("start_value must be positive and years must be greater than zero.")
    return (((end_value / start_value) ** (1 / years)) - 1) * 100


def calculate_future_revenue(current_revenue: float, cagr: float, years: int) -> float:
    return current_revenue * ((1 + cagr) ** years)


def calculate_future_fcf(future_revenue: float, fcf_margin: float) -> float:
    return future_revenue * fcf_margin


def calculate_expected_return(current_share_price: float, future_share_price: float, years: int) -> float:
    if current_share_price <= 0 or years <= 0:
        raise ValueError("current_share_price must be positive and years must be greater than zero.")
    return (future_share_price / current_share_price) ** (1 / years) - 1


def calculate_valuation(
    current_revenue: float,
    cagr: float,
    years: int,
    terminal_revenue: float,
    operating_margin: float,
    fcf_margin: float,
    terminal_multiple: float,
    cash: float,
    debt: float,
    current_share_price: float,
):
    future_revenue = calculate_future_revenue(current_revenue, cagr, years)
    future_fcf = calculate_future_fcf(future_revenue, fcf_margin)
    future_equity_value = (future_fcf * terminal_multiple) + cash - debt
    implied_share_price = future_equity_value / max(current_revenue, 1)
    expected_return = calculate_expected_return(current_share_price, implied_share_price, years)

    return {
        "future_revenue": future_revenue,
        "future_fcf": future_fcf,
        "equity_value": future_equity_value,
        "implied_share_price": implied_share_price,
        "expected_return": expected_return,
    }
