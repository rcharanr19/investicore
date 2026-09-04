from __future__ import annotations

from repositories.analysis_repository import AnalysisRepository
from repositories.company_repository import CompanyRepository
from repositories.financial_repository import FinancialRepository
from repositories.growth_driver_repository import GrowthDriverRepository
from repositories.risk_repository import RiskRepository
from repositories.scenario_repository import ScenarioRepository
from repositories.thesis_breaker_repository import ThesisBreakerRepository
from services.framework import load_framework

company_repository = CompanyRepository()
analysis_repository = AnalysisRepository()
financial_repository = FinancialRepository()
scenario_repository = ScenarioRepository()
risk_repository = RiskRepository()
thesis_breaker_repository = ThesisBreakerRepository()
growth_driver_repository = GrowthDriverRepository()


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

    # Seed 3 years of financial history for META (Annual)
    financial_repository.create_or_update(company["id"], 2023, {
        "revenue": 134900.0,
        "gross_profit": 108900.0,
        "operating_income": 46750.0,
        "net_income": 39098.0,
        "eps": 14.87,
        "operating_cash_flow": 71110.0,
        "free_cash_flow": 43010.0,
        "capex": 28100.0,
        "rnd": 38480.0,
        "sbc": 12740.0,
        "cash": 65400.0,
        "debt": 18390.0,
        "shares_outstanding": 2570.0,
    }, period_type="Annual")
    financial_repository.create_or_update(company["id"], 2024, {
        "revenue": 160000.0,
        "gross_profit": 130000.0,
        "operating_income": 58000.0,
        "net_income": 48000.0,
        "eps": 18.50,
        "operating_cash_flow": 88000.0,
        "free_cash_flow": 51000.0,
        "capex": 37000.0,
        "rnd": 42000.0,
        "sbc": 14000.0,
        "cash": 72000.0,
        "debt": 18400.0,
        "shares_outstanding": 2530.0,
    }, period_type="Annual")
    financial_repository.create_or_update(company["id"], 2025, {
        "revenue": 185000.0,
        "gross_profit": 152000.0,
        "operating_income": 70000.0,
        "net_income": 59000.0,
        "eps": 23.20,
        "operating_cash_flow": 103000.0,
        "free_cash_flow": 61000.0,
        "capex": 42000.0,
        "rnd": 48000.0,
        "sbc": 15500.0,
        "cash": 78000.0,
        "debt": 18500.0,
        "shares_outstanding": 2500.0,
    }, period_type="Annual")

    # Seed 4 quarters of 2025 for META (Quarterly)
    q_data = [
        (1, 42000.0, 34000.0, 15500.0, 13000.0, 5.10, 24000.0, 13500.0),
        (2, 45000.0, 37000.0, 17000.0, 14200.0, 5.60, 25300.0, 14800.0),
        (3, 47500.0, 39000.0, 18200.0, 15300.0, 6.00, 26200.0, 15700.0),
        (4, 50500.0, 42000.0, 19300.0, 16500.0, 6.50, 27500.0, 17000.0),
    ]
    for q_num, q_rev, q_gp, q_op, q_net, q_eps, q_ocf, q_fcf in q_data:
        financial_repository.create_or_update(company["id"], 2025, {
            "period_type": "Quarterly",
            "fiscal_quarter": q_num,
            "revenue": q_rev,
            "gross_profit": q_gp,
            "operating_income": q_op,
            "net_income": q_net,
            "eps": q_eps,
            "operating_cash_flow": q_ocf,
            "free_cash_flow": q_fcf,
            "capex": 10500.0,
            "rnd": 12000.0,
            "sbc": 3875.0,
            "cash": 78000.0,
            "debt": 18500.0,
            "shares_outstanding": 2500.0,
        }, period_type="Quarterly", fiscal_quarter=q_num)


    if analysis:
        aid = analysis["id"]
        scenario_repository.save_scenarios(aid, {
            "Bear": {"probability": 25, "revenue_cagr": 0.05, "forecast_period": 5, "fcf_margin": 0.25, "terminal_multiple": 12.0},
            "Base": {"probability": 50, "revenue_cagr": 0.12, "forecast_period": 5, "fcf_margin": 0.30, "terminal_multiple": 16.0},
            "Bull": {"probability": 25, "revenue_cagr": 0.18, "forecast_period": 5, "fcf_margin": 0.35, "terminal_multiple": 20.0},
        })

        # Seed Risks
        risk_repository.create_or_update(aid, {
            "risk": "Ad spending slowdown from macroeconomic weakness",
            "category": "Macroeconomic",
            "probability": 40,
            "impact": 6,
            "mitigation": "Diversify ad formats and expand Reels monetization",
            "status": "Active",
        })
        risk_repository.create_or_update(aid, {
            "risk": "Regulatory fines or data privacy restrictions in EU",
            "category": "Regulation",
            "probability": 50,
            "impact": 5,
            "mitigation": "Paid ad-free tier offering in EU",
            "status": "Active",
        })

        # Seed Thesis Breakers
        thesis_breaker_repository.create_or_update(aid, {
            "condition": "Family Daily Active People (DAP) declines Y/Y for 2 consecutive quarters",
            "metric": "DAP Growth",
            "operator": "<",
            "threshold": 0.0,
            "current_value": 5.0,
            "current_status": "Not Triggered",
        })
        thesis_breaker_repository.create_or_update(aid, {
            "condition": "Reality Labs operating loss exceeds $25B annually",
            "metric": "RL Op Loss ($B)",
            "operator": ">",
            "threshold": 25.0,
            "current_value": 16.0,
            "current_status": "Not Triggered",
        })

        # Seed Growth Drivers
        growth_driver_repository.create_or_update(company["id"], {
            "name": "Family Daily Active People (DAP)",
            "description": "Global active users across Facebook, IG, WhatsApp, Threads",
            "unit": "Billions",
            "current_value": 3.27,
            "confidence": 85,
            "notes": "Core engagement driver",
        })


def add_company(data: dict):
    return company_repository.create(data)


def list_companies():
    return company_repository.list_all()


def list_analyses():
    return analysis_repository.list_all()


def create_analysis(data: dict):
    return analysis_repository.create(data)
