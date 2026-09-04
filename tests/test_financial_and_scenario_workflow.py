import pytest
from repositories.financial_repository import FinancialRepository
from repositories.scenario_repository import ScenarioRepository


def test_financial_repository_operations():
    repo = FinancialRepository()
    company_id = "company-fin-1"

    repo.create_or_update(company_id, 2023, {"revenue": 100.0, "free_cash_flow": 20.0})
    repo.create_or_update(company_id, 2024, {"revenue": 115.0, "free_cash_flow": 25.0})
    repo.create_or_update(company_id, 2025, {"revenue": 132.25, "free_cash_flow": 30.0})

    history = repo.get_by_company(company_id)
    assert len(history) == 3
    assert history[0]["fiscal_year"] == 2023
    assert history[-1]["fiscal_year"] == 2025

    latest = repo.get_latest(company_id)
    assert latest["fiscal_year"] == 2025
    assert latest["revenue"] == 132.25

    cagr = repo.calculate_historical_cagr(company_id, "revenue")
    assert cagr is not None
    assert round(cagr, 2) == 15.00


def test_scenario_repository_operations_and_calculations():
    scenario_repo = ScenarioRepository()
    analysis_id = "analysis-scen-1"

    scenarios = {
        "Bear": {"probability": 20, "revenue_cagr": 0.05, "forecast_period": 5, "fcf_margin": 0.20, "terminal_multiple": 10.0},
        "Base": {"probability": 60, "revenue_cagr": 0.10, "forecast_period": 5, "fcf_margin": 0.25, "terminal_multiple": 15.0},
        "Bull": {"probability": 20, "revenue_cagr": 0.15, "forecast_period": 5, "fcf_margin": 0.30, "terminal_multiple": 20.0},
    }

    scenario_repo.save_scenarios(analysis_id, scenarios)
    retrieved = scenario_repo.get_scenarios(analysis_id)
    assert "Base" in retrieved
    assert retrieved["Base"]["probability"] == 60

    result = scenario_repo.calculate_scenario_outputs(
        analysis_id,
        current_revenue=1000.0,
        current_share_price=100.0,
        cash=100.0,
        debt=50.0,
        shares_outstanding=50.0,
    )

    assert "Bear" in result["scenarios"]
    assert "Base" in result["scenarios"]
    assert "Bull" in result["scenarios"]
    assert result["weighted_implied_share_price"] > 0
    assert result["weighted_expected_return"] != 0.0


def test_scenario_repository_invalid_probabilities_raises():
    scenario_repo = ScenarioRepository()
    analysis_id = "analysis-scen-bad"

    invalid_scenarios = {
        "Bear": {"probability": 30, "revenue_cagr": 0.05},
        "Base": {"probability": 50, "revenue_cagr": 0.10},
        "Bull": {"probability": 30, "revenue_cagr": 0.15},  # Sum = 110%
    }

    with pytest.raises(ValueError, match="Scenario probabilities must total exactly 100%"):
        scenario_repo.save_scenarios(analysis_id, invalid_scenarios)
