from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def calculate_cigar_butt_score(
    price_to_ncav: float | None,
    current_ratio: float | None,
    net_cash: float | None,
    fcf: float | None,
    cash_runway_years: float | None,
    share_dilution_cagr: float | None,
    catalyst_probability: float | None = None,
    has_active_catalyst: bool = False,
    management_score_override: float | None = None,
) -> dict[str, Any]:
    """Calculate 100-point InvestiCore Research Score for Cigar-Butt / Net-Net candidates.

    Weighting:
    - Asset Discount (0-25 pts)
    - Balance Sheet Strength (0-20 pts)
    - Cash Burn & Runway (0-15 pts)
    - Catalyst Quality (0-20 pts)
    - Management & Capital Allocation (0-10 pts)
    - Dilution Risk (0-10 pts)
    """

    # 1. Asset Discount (25 pts)
    asset_pts = 0.0
    if price_to_ncav is not None and price_to_ncav > 0:
        if price_to_ncav <= 0.67:
            asset_pts = 25.0
        elif price_to_ncav <= 0.80:
            asset_pts = 20.0
        elif price_to_ncav <= 1.00:
            asset_pts = 15.0
        elif price_to_ncav <= 1.25:
            asset_pts = 8.0
        elif price_to_ncav <= 1.50:
            asset_pts = 4.0
        else:
            asset_pts = 0.0

    # 2. Balance Sheet Strength (20 pts)
    bs_pts = 0.0
    cr = float(current_ratio or 0.0)
    nc = float(net_cash or 0.0)

    if cr >= 3.0:
        bs_pts += 10.0
    elif cr >= 2.0:
        bs_pts += 8.0
    elif cr >= 1.5:
        bs_pts += 5.0
    elif cr >= 1.0:
        bs_pts += 2.0

    if nc > 0:
        bs_pts += 10.0
    elif nc == 0:
        bs_pts += 5.0
    else:
        bs_pts += 0.0

    # 3. Cash Burn & Runway (15 pts)
    burn_pts = 0.0
    if fcf is not None and fcf >= 0:
        burn_pts = 15.0
    elif cash_runway_years is not None:
        if cash_runway_years >= 4.0:
            burn_pts = 12.0
        elif cash_runway_years >= 2.0:
            burn_pts = 8.0
        elif cash_runway_years >= 1.0:
            burn_pts = 4.0
        else:
            burn_pts = 0.0
    else:
        burn_pts = 5.0

    # 4. Catalyst Quality (20 pts)
    cat_pts = 0.0
    prob = float(catalyst_probability or 0.0)
    if has_active_catalyst:
        if prob >= 75.0:
            cat_pts = 20.0
        elif prob >= 50.0:
            cat_pts = 14.0
        elif prob >= 25.0:
            cat_pts = 8.0
        else:
            cat_pts = 4.0
    else:
        cat_pts = 0.0

    # 5. Management & Capital Allocation (10 pts)
    if management_score_override is not None:
        mgmt_pts = max(0.0, min(10.0, float(management_score_override)))
    else:
        mgmt_pts = 6.0  # Default neutral

    # 6. Dilution Risk (10 pts)
    dilution_pts = 0.0
    if share_dilution_cagr is not None:
        if share_dilution_cagr < -0.5:
            dilution_pts = 10.0  # Accretive share buybacks
        elif share_dilution_cagr <= 1.5:
            dilution_pts = 8.0
        elif share_dilution_cagr <= 4.0:
            dilution_pts = 5.0
        elif share_dilution_cagr <= 8.0:
            dilution_pts = 2.0
        else:
            dilution_pts = 0.0
    else:
        dilution_pts = 5.0

    total_score = round(asset_pts + bs_pts + burn_pts + cat_pts + mgmt_pts + dilution_pts, 1)

    # Classification
    if total_score >= 80.0:
        rating = "Highly Attractive Opportunity"
    elif total_score >= 65.0:
        rating = "Interesting Net-Net Candidate"
    elif total_score >= 50.0:
        rating = "Speculative / Watch"
    else:
        rating = "High Risk / Avoid"

    return {
        "cigar_butt_score": total_score,
        "rating": rating,
        "component_breakdown": {
            "asset_discount": round(asset_pts, 1),
            "balance_sheet": round(bs_pts, 1),
            "cash_burn": round(burn_pts, 1),
            "catalyst": round(cat_pts, 1),
            "management": round(mgmt_pts, 1),
            "dilution_risk": round(dilution_pts, 1),
        },
        "max_points": {
            "asset_discount": 25,
            "balance_sheet": 20,
            "cash_burn": 15,
            "catalyst": 20,
            "management": 10,
            "dilution_risk": 10,
        },
    }


def perform_forensic_checks(
    rev_growth_pct: float | None,
    inv_growth_pct: float | None,
    rec_growth_pct: float | None,
    goodwill: float | None,
    total_assets: float | None,
    cash_burn_runway_years: float | None,
    dilution_cagr: float | None,
) -> list[dict[str, Any]]:
    """Runs automated forensic checks across balance sheet and working capital metrics."""
    flags: list[dict[str, Any]] = []

    # 1. Inventory Divergence (Inventory growing much faster than sales)
    if inv_growth_pct is not None and rev_growth_pct is not None:
        div = inv_growth_pct - rev_growth_pct
        if div > 25.0:
            flags.append({
                "severity": "CRITICAL",
                "category": "Inventory Forensics",
                "headline": "Inventory Growth Significantly Outpacing Revenue",
                "detail": f"Inventory grew {inv_growth_pct:+.1f}% while Revenue changed {rev_growth_pct:+.1f}% (divergence of {div:+.1f}%). Risk of obsolete inventory or write-downs.",
            })
        elif div > 15.0:
            flags.append({
                "severity": "WARNING",
                "category": "Inventory Forensics",
                "headline": "Moderate Inventory Build-up",
                "detail": f"Inventory growth ({inv_growth_pct:+.1f}%) exceeds revenue growth ({rev_growth_pct:+.1f}%).",
            })

    # 2. Receivables Divergence (Channel stuffing risk)
    if rec_growth_pct is not None and rev_growth_pct is not None:
        div_rec = rec_growth_pct - rev_growth_pct
        if div_rec > 20.0:
            flags.append({
                "severity": "WARNING",
                "category": "Receivables Forensics",
                "headline": "Receivables Growing Faster Than Revenue",
                "detail": f"Accounts Receivable grew {rec_growth_pct:+.1f}% vs Revenue {rev_growth_pct:+.1f}%. May indicate customer collection slowdown or aggressive credit terms.",
            })

    # 3. Goodwill / Intangible Heavy Balance Sheet
    if goodwill is not None and total_assets is not None and total_assets > 0:
        gw_pct = (goodwill / total_assets) * 100.0
        if gw_pct > 40.0:
            flags.append({
                "severity": "WARNING",
                "category": "Asset Quality",
                "headline": "High Goodwill Concentration",
                "detail": f"Goodwill represents {gw_pct:.1f}% of Total Assets. Intangibles provide zero downside liquidation support.",
            })

    # 4. Critical Cash Runway
    if cash_burn_runway_years is not None and cash_burn_runway_years < 1.0:
        flags.append({
            "severity": "CRITICAL",
            "category": "Solvency / Cash Burn",
            "headline": "Severe Cash Runway (< 1 Year)",
            "detail": f"At current burn rate, available cash & securities will be exhausted in {cash_burn_runway_years:.1f} years without outside capital.",
        })

    # 5. Heavy Share Dilution
    if dilution_cagr is not None and dilution_cagr > 6.0:
        flags.append({
            "severity": "WARNING",
            "category": "Dilution",
            "headline": "High Share Count Expansion",
            "detail": f"Shares outstanding expanding at {dilution_cagr:.1f}% CAGR, significantly diluting per-share NCAV downside protection.",
        })

    return flags
