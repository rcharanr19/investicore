from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NCAVAssumptions:
    """Configurable asset recovery and haircut assumptions for Net-Net / Liquidation valuation."""

    cash_recovery: float = 1.00
    marketable_securities_recovery: float = 1.00
    receivables_recovery: float = 0.75
    inventory_recovery: float = 0.50
    other_current_assets_recovery: float = 0.00
    ppe_recovery: float = 0.15
    goodwill_recovery: float = 0.00
    intangibles_recovery: float = 0.00
    other_noncurrent_assets_recovery: float = 0.00
    liquidation_costs: float = 0.00
    off_balance_sheet_obligations: float = 0.00


def calculate_ncav(
    current_assets: float | None,
    total_liabilities: float | None,
) -> float | None:
    """Calculate traditional Net Current Asset Value (NCAV).

    Formula: Total Current Assets - Total Liabilities
    Data Safety: Returns None if either input is None (missing data != zero).
    """
    if current_assets is None or total_liabilities is None:
        return None
    return float(current_assets) - float(total_liabilities)


def calculate_ncav_per_share(
    ncav: float | None,
    shares_outstanding: float | None,
) -> float | None:
    """Calculate NCAV Per Share.

    Formula: NCAV / Diluted Shares Outstanding
    """
    if ncav is None or shares_outstanding is None or shares_outstanding <= 0:
        return None
    return float(ncav) / float(shares_outstanding)


def calculate_price_to_ncav(
    share_price: float | None,
    ncav_per_share: float | None,
) -> float | None:
    """Calculate Price / NCAV.

    Formula: Current Share Price / NCAV Per Share
    """
    if share_price is None or ncav_per_share is None or ncav_per_share == 0:
        return None
    return float(share_price) / float(ncav_per_share)


def calculate_net_cash(
    cash: float | None,
    marketable_securities: float | None,
    total_debt: float | None,
) -> float | None:
    """Calculate Net Cash.

    Formula: Cash + Marketable Securities - Total Debt
    """
    if cash is None and marketable_securities is None and total_debt is None:
        return None
    c = float(cash or 0.0)
    ms = float(marketable_securities or 0.0)
    d = float(total_debt or 0.0)
    return c + ms - d


def calculate_nnwc(
    cash: float | None,
    marketable_securities: float | None,
    accounts_receivable: float | None,
    inventory: float | None,
    other_current_assets: float | None,
    total_liabilities: float | None,
    assumptions: NCAVAssumptions | None = None,
) -> float | None:
    """Calculate Net-Net Working Capital (NNWC) with conservative asset haircuts.

    Default Formula:
      (100% * Cash) + (100% * Marketable Securities) + (75% * Receivables)
      + (50% * Inventory) + (0% * Other Current Assets) - Total Liabilities
    """
    if total_liabilities is None:
        return None
    # Must have at least cash or current asset information
    if cash is None and accounts_receivable is None and inventory is None:
        return None

    a = assumptions or NCAVAssumptions()
    c = float(cash or 0.0) * a.cash_recovery
    ms = float(marketable_securities or 0.0) * a.marketable_securities_recovery
    ar = float(accounts_receivable or 0.0) * a.receivables_recovery
    inv = float(inventory or 0.0) * a.inventory_recovery
    oca = float(other_current_assets or 0.0) * a.other_current_assets_recovery

    adjusted_current_assets = c + ms + ar + inv + oca
    return adjusted_current_assets - float(total_liabilities)


def calculate_adjusted_liquidation_value(
    cash: float | None,
    marketable_securities: float | None,
    accounts_receivable: float | None,
    inventory: float | None,
    other_current_assets: float | None,
    ppe: float | None,
    goodwill: float | None,
    intangibles: float | None,
    other_assets: float | None,
    total_liabilities: float | None,
    assumptions: NCAVAssumptions | None = None,
) -> float | None:
    """Calculate Adjusted Liquidation Value across all balance sheet asset classes."""
    if total_liabilities is None:
        return None

    a = assumptions or NCAVAssumptions()
    c = float(cash or 0.0) * a.cash_recovery
    ms = float(marketable_securities or 0.0) * a.marketable_securities_recovery
    ar = float(accounts_receivable or 0.0) * a.receivables_recovery
    inv = float(inventory or 0.0) * a.inventory_recovery
    oca = float(other_current_assets or 0.0) * a.other_current_assets_recovery
    ppe_val = float(ppe or 0.0) * a.ppe_recovery
    gw_val = float(goodwill or 0.0) * a.goodwill_recovery
    int_val = float(intangibles or 0.0) * a.intangibles_recovery
    oa_val = float(other_assets or 0.0) * a.other_noncurrent_assets_recovery

    total_realizable_assets = c + ms + ar + inv + oca + ppe_val + gw_val + int_val + oa_val
    liquidation_val = total_realizable_assets - float(total_liabilities) - a.liquidation_costs - a.off_balance_sheet_obligations
    return liquidation_val


def calculate_cash_burn_and_runway(
    cash_and_equivalents: float | None,
    marketable_securities: float | None,
    operating_cash_flow: float | None,
    capex: float | None,
) -> dict[str, Any]:
    """Analyze historical cash burn, free cash flow, and runway in years."""
    if operating_cash_flow is None:
        return {
            "free_cash_flow": None,
            "annual_cash_burn": None,
            "cash_runway_years": None,
            "burn_status": "Unknown (Missing OCF)",
        }

    fcf = float(operating_cash_flow) - float(capex or 0.0)
    total_liquid_cash = float(cash_and_equivalents or 0.0) + float(marketable_securities or 0.0)

    if fcf >= 0:
        return {
            "free_cash_flow": fcf,
            "annual_cash_burn": 0.0,
            "cash_runway_years": float("inf"),
            "burn_status": "Positive FCF (Self-funding)",
        }

    annual_burn = abs(fcf)
    runway = (total_liquid_cash / annual_burn) if annual_burn > 0 else float("inf")

    if runway < 1.0:
        status = "Critical Burn (< 1 year)"
    elif runway < 2.0:
        status = "High Burn (1-2 years)"
    elif runway < 4.0:
        status = "Moderate Burn (2-4 years)"
    else:
        status = "Low Burn (> 4 years)"

    return {
        "free_cash_flow": fcf,
        "annual_cash_burn": annual_burn,
        "cash_runway_years": round(runway, 2),
        "burn_status": status,
    }


def calculate_share_dilution(
    start_shares: float | None,
    end_shares: float | None,
    years: float = 1.0,
) -> dict[str, Any]:
    """Calculate annualized share dilution rate and classification."""
    if start_shares is None or end_shares is None or start_shares <= 0 or end_shares <= 0 or years <= 0:
        return {
            "dilution_pct": None,
            "annualized_rate": None,
            "classification": "Insufficient Data",
        }

    total_change_pct = ((end_shares - start_shares) / start_shares) * 100.0
    cagr = (((end_shares / start_shares) ** (1.0 / years)) - 1.0) * 100.0

    if cagr < -0.5:
        classification = "Share Reduction (Accretive Buybacks)"
    elif cagr <= 2.0:
        classification = "Stable Share Count"
    elif cagr <= 5.0:
        classification = "Moderate Dilution"
    else:
        classification = "High Dilution Risk"

    return {
        "dilution_pct": round(total_change_pct, 2),
        "annualized_rate": round(cagr, 2),
        "classification": classification,
    }


def calculate_scenario_expected_value(
    bear_price: float,
    bear_prob: float,
    base_price: float,
    base_prob: float,
    bull_price: float,
    bull_prob: float,
    current_price: float,
    years: float = 1.0,
) -> dict[str, Any]:
    """Calculate probability-weighted Expected Value, Expected Return, and Annualized Return."""
    total_prob = bear_prob + base_prob + bull_prob
    if total_prob <= 0:
        w_bear, w_base, w_bull = 0.25, 0.50, 0.25
    else:
        w_bear = bear_prob / total_prob
        w_base = base_prob / total_prob
        w_bull = bull_prob / total_prob

    expected_val = (bear_price * w_bear) + (base_price * w_base) + (bull_price * w_bull)

    if current_price > 0:
        expected_return_pct = ((expected_val / current_price) - 1.0) * 100.0
        if expected_val > 0 and years > 0:
            annualized_return_pct = (((expected_val / current_price) ** (1.0 / years)) - 1.0) * 100.0
        else:
            annualized_return_pct = expected_return_pct
    else:
        expected_return_pct = 0.0
        annualized_return_pct = 0.0

    return {
        "expected_value": round(expected_val, 2),
        "expected_return_pct": round(expected_return_pct, 2),
        "annualized_return_pct": round(annualized_return_pct, 2),
        "bear_weight": round(w_bear * 100, 1),
        "base_weight": round(w_base * 100, 1),
        "bull_weight": round(w_bull * 100, 1),
    }
