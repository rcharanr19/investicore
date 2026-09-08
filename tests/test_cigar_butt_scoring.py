from __future__ import annotations

import pytest

from services.cigar_butt_scoring import calculate_cigar_butt_score, perform_forensic_checks


def test_calculate_cigar_butt_score_high_quality():
    # Deep net-net with net cash, positive FCF, active catalyst, buybacks
    score = calculate_cigar_butt_score(
        price_to_ncav=0.60,  # <= 0.67 -> 25 pts
        current_ratio=3.5,  # >= 3.0 -> 10 pts
        net_cash=50.0,  # > 0 -> 10 pts (total balance sheet = 20)
        fcf=15.0,  # >= 0 -> 15 pts
        cash_runway_years=float("inf"),
        share_dilution_cagr=-2.0,  # < -0.5 -> 10 pts
        catalyst_probability=80.0,  # >= 75% -> 20 pts
        has_active_catalyst=True,
        management_score_override=8.0,  # 8 pts
    )

    assert score["cigar_butt_score"] == 98.0
    assert "Highly Attractive" in score["rating"]
    assert score["component_breakdown"]["asset_discount"] == 25.0
    assert score["component_breakdown"]["balance_sheet"] == 20.0
    assert score["component_breakdown"]["cash_burn"] == 15.0
    assert score["component_breakdown"]["catalyst"] == 20.0


def test_calculate_cigar_butt_score_poor_candidate():
    # Expensive price/ncav, burning cash < 1 yr runway, heavy dilution, no catalyst
    score = calculate_cigar_butt_score(
        price_to_ncav=2.50,  # 0 pts
        current_ratio=0.8,  # 0 pts
        net_cash=-40.0,  # 0 pts
        fcf=-25.0,  # 0 pts
        cash_runway_years=0.5,  # 0 pts
        share_dilution_cagr=15.0,  # > 8% -> 0 pts
        has_active_catalyst=False,
        management_score_override=3.0,
    )

    assert score["cigar_butt_score"] == 3.0
    assert "High Risk" in score["rating"]


def test_perform_forensic_checks_flags():
    flags = perform_forensic_checks(
        rev_growth_pct=-5.0,
        inv_growth_pct=30.0,  # Divergence = 35% -> CRITICAL
        rec_growth_pct=25.0,  # Divergence = 30% -> WARNING
        goodwill=60.0,
        total_assets=100.0,  # GW is 60% of TA -> WARNING
        cash_burn_runway_years=0.75,  # < 1 yr -> CRITICAL
        dilution_cagr=8.5,  # > 6% -> WARNING
    )

    assert len(flags) == 5
    severities = {f["severity"] for f in flags}
    assert "CRITICAL" in severities
    assert "WARNING" in severities
    assert any("Inventory" in f["headline"] for f in flags)
    assert any("Cash Runway" in f["headline"] for f in flags)
