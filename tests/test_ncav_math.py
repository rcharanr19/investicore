from __future__ import annotations

import pytest

from services.ncav import (
    NCAVAssumptions,
    calculate_adjusted_liquidation_value,
    calculate_cash_burn_and_runway,
    calculate_ncav,
    calculate_ncav_per_share,
    calculate_net_cash,
    calculate_nnwc,
    calculate_price_to_ncav,
    calculate_scenario_expected_value,
    calculate_share_dilution,
)


def test_traditional_ncav_standard():
    # Current Assets: $150M, Total Liabilities: $90M -> NCAV = $60M
    ncav = calculate_ncav(150.0, 90.0)
    assert ncav == 60.0

    # NCAV Per share with 10M shares -> $6.00 / share
    ncav_ps = calculate_ncav_per_share(ncav, 10.0)
    assert ncav_ps == 6.0

    # Price / NCAV at $4.50 share price -> 0.75 (25% discount)
    p_ncav = calculate_price_to_ncav(4.50, ncav_ps)
    assert p_ncav == 0.75


def test_ncav_negative_and_edge_cases():
    # Negative NCAV: Current Assets $50M, Liabilities $80M -> -$30M
    neg_ncav = calculate_ncav(50.0, 80.0)
    assert neg_ncav == -30.0

    # Per share with negative NCAV
    neg_ps = calculate_ncav_per_share(neg_ncav, 10.0)
    assert neg_ps == -3.0

    # Missing data must return None (Data safety: Missing != zero)
    assert calculate_ncav(None, 80.0) is None
    assert calculate_ncav(100.0, None) is None
    assert calculate_ncav_per_share(60.0, 0.0) is None
    assert calculate_ncav_per_share(60.0, -5.0) is None
    assert calculate_price_to_ncav(10.0, 0.0) is None
    assert calculate_price_to_ncav(None, 5.0) is None


def test_net_cash_calculation():
    # Cash $40M, Marketable Securities $20M, Debt $15M -> Net Cash $45M
    net_cash = calculate_net_cash(40.0, 20.0, 15.0)
    assert net_cash == 45.0

    # Net Debt situation: Cash $10M, Debt $50M -> -$40M
    net_debt = calculate_net_cash(10.0, 0.0, 50.0)
    assert net_debt == -40.0


def test_nnwc_conservative_haircuts():
    # Cash: $20M (100% = 20M)
    # Marketable Securities: $10M (100% = 10M)
    # Accounts Receivable: $40M (75% = 30M)
    # Inventory: $60M (50% = 30M)
    # Other Current Assets: $10M (0% = 0M)
    # Total Current Assets = $140M
    # Total Liabilities: $70M
    # Expected NNWC = 20 + 10 + 30 + 30 + 0 - 70 = $20M (whereas NCAV would be 140 - 70 = $70M)
    nnwc = calculate_nnwc(
        cash=20.0,
        marketable_securities=10.0,
        accounts_receivable=40.0,
        inventory=60.0,
        other_current_assets=10.0,
        total_liabilities=70.0,
    )
    assert nnwc == 20.0


def test_adjusted_liquidation_value():
    assumptions = NCAVAssumptions(
        cash_recovery=1.0,
        marketable_securities_recovery=1.0,
        receivables_recovery=0.75,
        inventory_recovery=0.50,
        other_current_assets_recovery=0.0,
        ppe_recovery=0.20,  # 20% on PP&E
        goodwill_recovery=0.0,
        intangibles_recovery=0.0,
        other_noncurrent_assets_recovery=0.0,
        liquidation_costs=5.0,  # $5M liquidation & wind-down expense
    )

    # Cash: 20M (20) + Rec: 40M (30) + Inv: 60M (30) + PPE: 50M (10) = 90M
    # Liabilities: 70M - Costs: 5M -> Liquidation Value = 90 - 70 - 5 = $15M
    liq_val = calculate_adjusted_liquidation_value(
        cash=20.0,
        marketable_securities=0.0,
        accounts_receivable=40.0,
        inventory=60.0,
        other_current_assets=10.0,
        ppe=50.0,
        goodwill=30.0,
        intangibles=10.0,
        other_assets=5.0,
        total_liabilities=70.0,
        assumptions=assumptions,
    )
    assert liq_val == 15.0


def test_cash_burn_and_runway():
    # Positive cash flow
    pos_res = calculate_cash_burn_and_runway(
        cash_and_equivalents=50.0,
        marketable_securities=10.0,
        operating_cash_flow=25.0,
        capex=10.0,
    )
    assert pos_res["free_cash_flow"] == 15.0
    assert "Positive FCF" in pos_res["burn_status"]

    # Critical burn: Cash $10M, Burning $15M/yr -> Runway = 0.67 yrs
    burn_res = calculate_cash_burn_and_runway(
        cash_and_equivalents=10.0,
        marketable_securities=0.0,
        operating_cash_flow=-10.0,
        capex=5.0,
    )
    assert burn_res["free_cash_flow"] == -15.0
    assert burn_res["cash_runway_years"] == 0.67
    assert "Critical Burn" in burn_res["burn_status"]


def test_share_dilution():
    # 10M shares to 12M shares over 2 years (20% total, ~9.54% CAGR)
    dilution = calculate_share_dilution(10.0, 12.0, years=2.0)
    assert dilution["dilution_pct"] == 20.0
    assert dilution["annualized_rate"] == 9.54
    assert dilution["classification"] == "High Dilution Risk"

    # Buybacks: 10M to 9M
    buyback = calculate_share_dilution(10.0, 9.0, years=1.0)
    assert buyback["dilution_pct"] == -10.0
    assert buyback["classification"] == "Share Reduction (Accretive Buybacks)"


def test_scenario_expected_value():
    res = calculate_scenario_expected_value(
        bear_price=5.0,
        bear_prob=25.0,
        base_price=10.0,
        base_prob=50.0,
        bull_price=18.0,
        bull_prob=25.0,
        current_price=8.0,
        years=2.0,
    )
    # Expected Val = (5 * 0.25) + (10 * 0.50) + (18 * 0.25) = 1.25 + 5.0 + 4.5 = 10.75
    assert res["expected_value"] == 10.75
    # Expected Return = (10.75 / 8.0) - 1 = +34.38%
    assert res["expected_return_pct"] == 34.38
    # Annualized Return = sqrt(1.34375) - 1 = +15.92%
    assert res["annualized_return_pct"] == 15.92
