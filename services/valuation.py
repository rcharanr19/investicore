from __future__ import annotations


def calculate_cagr(start_value: float, end_value: float, years: int) -> float:
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return 0.0
    try:
        return (((end_value / start_value) ** (1 / years)) - 1) * 100.0
    except Exception:
        return 0.0


def calculate_expected_cagr_pct(current_value: float, future_value: float, years: int) -> float:
    """Return expected annualized CAGR percentage between current and future value."""
    if current_value <= 0 or future_value <= 0 or years <= 0:
        return 0.0
    try:
        return (((future_value / current_value) ** (1 / years)) - 1) * 100.0
    except Exception:
        return 0.0


def calculate_percentage_change(start_value: float, end_value: float) -> float | None:
    if start_value == 0:
        return None
    try:
        return ((end_value - start_value) / abs(start_value)) * 100.0
    except Exception:
        return None


def calculate_future_revenue(current_revenue: float, cagr: float, years: int) -> float:
    return current_revenue * ((1 + cagr) ** years)


def calculate_future_fcf(future_revenue: float, fcf_margin: float) -> float:
    return future_revenue * fcf_margin


def calculate_expected_return(current_share_price: float, future_share_price: float, years: int) -> float:
    if current_share_price <= 0 or future_share_price <= 0 or years <= 0:
        return 0.0
    try:
        return (future_share_price / current_share_price) ** (1 / years) - 1.0
    except Exception:
        return 0.0


def calculate_return_decomposition(
    expected_cagr_pct: float,
    growth_contribution_pct: float,
    capital_returns_pct: float,
    multiple_expansion_pct: float,
    asset_realization_pct: float | None = None,
    cash_accumulation_pct: float | None = None,
) -> dict:
    """Explain expected return in a deterministic, auditable decomposition.

    This keeps the expected return explicit and makes the return drivers easy to compare
    against the investment thesis.
    """
    components = {
        "growth_contribution_pct": growth_contribution_pct,
        "capital_returns_pct": capital_returns_pct,
        "multiple_expansion_pct": multiple_expansion_pct,
    }

    if asset_realization_pct is not None:
        components["asset_realization_pct"] = asset_realization_pct
    if cash_accumulation_pct is not None:
        components["cash_accumulation_pct"] = cash_accumulation_pct

    total_contribution = sum(float(v) for v in components.values())
    reconciliation_gap = float(expected_cagr_pct) - total_contribution

    return {
        "expected_cagr_pct": float(expected_cagr_pct),
        "components": components,
        "total_contribution_pct": round(total_contribution, 4),
        "reconciliation_gap_pct": round(reconciliation_gap, 4),
    }


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
