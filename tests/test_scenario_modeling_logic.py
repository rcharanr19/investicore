from repositories.growth_driver_repository import GrowthDriverRepository
from repositories.risk_repository import RiskRepository
from repositories.thesis_breaker_repository import ThesisBreakerRepository
from services.scenario_engine import calculate_risk_adjusted_valuation, generate_sensitivity_matrix


def test_sensitivity_matrix_generation():
    sens = generate_sensitivity_matrix(
        current_revenue=1000.0,
        current_share_price=100.0,
        cagr=0.10,
        years=5,
        fcf_margins=[0.20, 0.30],
        terminal_multiples=[15.0, 20.0],
        cash=100.0,
        debt=50.0,
        shares_outstanding=50.0,
    )

    assert len(sens["implied_price_matrix"]) == 2  # 2 FCF margin rows
    assert len(sens["implied_price_matrix"][0]) == 2  # 2 terminal multiple cols
    # Higher FCF margin and higher multiple should yield higher price
    assert sens["implied_price_matrix"][1][1] > sens["implied_price_matrix"][0][0]


def test_risk_repository_aggregate_score():
    risk_repo = RiskRepository()
    analysis_id = "test-analysis-risk"

    # Low risk
    risk_repo.create_or_update(analysis_id, {"probability": 20, "impact": 3})
    score_low_risk = risk_repo.calculate_aggregate_risk_score(analysis_id)
    assert score_low_risk > 8.0  # Quality risk component is high (good quality)

    # High risk
    risk_repo.create_or_update(analysis_id, {"probability": 80, "impact": 9})
    score_mixed_risk = risk_repo.calculate_aggregate_risk_score(analysis_id)
    assert score_mixed_risk < score_low_risk


def test_thesis_breaker_auto_triggering():
    breaker_repo = ThesisBreakerRepository()
    analysis_id = "test-analysis-breaker"

    breaker_repo.create_or_update(analysis_id, {
        "condition": "Revenue growth < 5%",
        "metric": "Revenue Growth",
        "operator": "<",
        "threshold": 5.0,
        "current_value": 2.0,  # Below threshold -> Triggered
    })

    status = breaker_repo.check_breakers_status(analysis_id)
    assert status["has_triggered"] is True
    assert status["triggered_count"] == 1


def test_risk_adjusted_valuation_calculation():
    res_normal = calculate_risk_adjusted_valuation(
        weighted_implied_price=200.0,
        risk_score=8.0,
        thesis_breakers_triggered=False,
    )
    assert res_normal["max_recommended_buy_price"] < 200.0

    res_triggered = calculate_risk_adjusted_valuation(
        weighted_implied_price=200.0,
        risk_score=8.0,
        thesis_breakers_triggered=True,
    )
    # Triggered thesis breaker should increase required MOS and lower max buy price
    assert res_triggered["max_recommended_buy_price"] < res_normal["max_recommended_buy_price"]


def test_growth_driver_repository():
    gd_repo = GrowthDriverRepository()
    company_id = "company-gd-1"

    gd_repo.create_or_update(company_id, {
        "name": "Active Users",
        "current_value": 100.0,
        "confidence": 90,
    })

    impact = gd_repo.calculate_implied_growth_impact(company_id)
    assert impact > 0.05
