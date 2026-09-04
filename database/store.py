from __future__ import annotations

from repositories.analysis_repository import AnalysisRepository
from repositories.company_repository import CompanyRepository
from repositories.financial_repository import FinancialRepository
from repositories.scenario_repository import ScenarioRepository
from services.framework import load_framework

company_repository = CompanyRepository()
analysis_repository = AnalysisRepository()
financial_repository = FinancialRepository()
scenario_repository = ScenarioRepository()


def seed_core_data() -> None:
    """Initialize global in-memory seed records for the local V1 app."""
    if company_repository.get_by_ticker("META") is not None:
        return

    company = company_repository.create(
        {
            "ticker": "META",
            "name": "Meta Platforms, Inc.",
            "sector": "Communication Services",
            "industry": "Internet Content & Information",
            "country": "United States",
            "description": "Sample company for the investment research platform.",
            "website": "https://about.meta.com",
            "status": "Watchlist",
        }
    )

    framework = load_framework()
    analysis = None
    if analysis_repository.get_latest_for_company(company["id"]) is None:
        analysis = analysis_repository.create(
            {
                "company_id": company["id"],
                "framework_version": "1.0",
                "analysis_date": "2026-09-04",
                "status": "Completed",
                "decision": "Buy",
                "confidence": 74,
                "overall_score": 8.10,
                "notes": "Training / Sample Analysis",
                "version_number": 1,
                "previous_analysis_id": None,
                "change_summary": "Initial training analysis",
                "framework": framework,
                "company": company,
            }
        )

    # Seed 3 years of financial history for META
    financial_repository.create_or_update(company["id"], 2023, {
        "revenue": 134900.0,
        "gross_profit": 108900.0,
        "operating_income": 46750.0,
        "net_income": 39098.0,
        "eps": 14.87,
        "free_cash_flow": 43010.0,
        "capex": 28100.0,
        "rnd": 38480.0,
        "sbc": 12740.0,
        "cash": 65400.0,
        "debt": 18390.0,
        "shares_outstanding": 2570.0,
    })
    financial_repository.create_or_update(company["id"], 2024, {
        "revenue": 160000.0,
        "gross_profit": 130000.0,
        "operating_income": 58000.0,
        "net_income": 48000.0,
        "eps": 18.50,
        "free_cash_flow": 51000.0,
        "capex": 37000.0,
        "rnd": 42000.0,
        "sbc": 14000.0,
        "cash": 72000.0,
        "debt": 18400.0,
        "shares_outstanding": 2530.0,
    })
    financial_repository.create_or_update(company["id"], 2025, {
        "revenue": 185000.0,
        "gross_profit": 152000.0,
        "operating_income": 70000.0,
        "net_income": 59000.0,
        "eps": 23.20,
        "free_cash_flow": 61000.0,
        "capex": 42000.0,
        "rnd": 48000.0,
        "sbc": 15500.0,
        "cash": 78000.0,
        "debt": 18500.0,
        "shares_outstanding": 2500.0,
    })

    if analysis:
        scenario_repository.save_scenarios(analysis["id"], {
            "Bear": {"probability": 25, "revenue_cagr": 0.05, "forecast_period": 5, "fcf_margin": 0.25, "terminal_multiple": 12.0},
            "Base": {"probability": 50, "revenue_cagr": 0.12, "forecast_period": 5, "fcf_margin": 0.30, "terminal_multiple": 16.0},
            "Bull": {"probability": 25, "revenue_cagr": 0.18, "forecast_period": 5, "fcf_margin": 0.35, "terminal_multiple": 20.0},
        })


def add_company(data: dict):
    return company_repository.create(data)


def list_companies():
    return company_repository.list_all()


def list_analyses():
    return analysis_repository.list_all()


def create_analysis(data: dict):
    return analysis_repository.create(data)
