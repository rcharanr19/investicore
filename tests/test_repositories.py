from repositories.company_repository import CompanyRepository
from repositories.analysis_repository import AnalysisRepository


def test_company_repository_crud():
    repo = CompanyRepository()
    company = repo.create({
        "ticker": "NVDA",
        "name": "NVIDIA",
        "sector": "Technology",
        "industry": "Semiconductors",
        "country": "United States",
        "description": "Sample company",
        "website": "https://nvidia.com",
        "status": "Watchlist",
    })

    assert company["ticker"] == "NVDA"
    assert repo.get_by_id(company["id"]) is not None
    assert repo.get_by_ticker("NVDA")["name"] == "NVIDIA"


def test_analysis_repository_versioning():
    repo = AnalysisRepository()
    company_id = "company-123"

    first = repo.create({
        "company_id": company_id,
        "framework_version": "1.0",
        "analysis_date": "2026-09-04",
        "status": "Completed",
        "decision": "Buy",
        "confidence": 70,
        "overall_score": 8.0,
        "notes": "v1",
        "version_number": 1,
        "previous_analysis_id": None,
        "change_summary": "Initial",
    })

    second = repo.create({
        "company_id": company_id,
        "framework_version": "1.0",
        "analysis_date": "2026-09-20",
        "status": "Completed",
        "decision": "Strong Buy",
        "confidence": 80,
        "overall_score": 8.5,
        "notes": "v2",
        "version_number": 2,
        "previous_analysis_id": first["id"],
        "change_summary": "Updated thesis",
    })

    versions = repo.get_versions_for_company(company_id)
    assert len(versions) >= 2
    assert versions[0]["version_number"] == 1
    assert versions[1]["version_number"] == 2
    assert versions[0]["notes"] == "v1"
