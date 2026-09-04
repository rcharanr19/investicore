from __future__ import annotations

from repositories.analysis_repository import AnalysisRepository
from repositories.company_repository import CompanyRepository
from services.framework import load_framework

company_repository = CompanyRepository()
analysis_repository = AnalysisRepository()


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
    if analysis_repository.get_latest_for_company(company["id"]) is None:
        analysis_repository.create(
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


def add_company(data: dict):
    return company_repository.create(data)


def list_companies():
    return company_repository.list_all()


def list_analyses():
    return analysis_repository.list_all()


def create_analysis(data: dict):
    return analysis_repository.create(data)
