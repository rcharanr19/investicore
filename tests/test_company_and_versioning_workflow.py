from repositories.analysis_repository import AnalysisRepository
from repositories.company_repository import CompanyRepository


def test_company_repository_workflow():
    repo = CompanyRepository()
    company = repo.create({
        "ticker": "MSFT",
        "name": "Microsoft",
        "sector": "Technology",
        "industry": "Software",
        "country": "United States",
        "description": "Cloud and productivity leader",
        "website": "https://microsoft.com",
        "status": "Watchlist",
    })

    assert repo.get_by_ticker("MSFT")["name"] == "Microsoft"
    assert len(repo.search("micro")) >= 1

    updated = repo.update(company["id"], {"name": "Microsoft Corp", "status": "Owned"})
    assert updated["name"] == "Microsoft Corp"
    assert updated["status"] == "Owned"

    repo.delete(company["id"])
    assert repo.get_by_id(company["id"]) is None


def test_analysis_versioning_keeps_historical_record_immutable():
    repo = AnalysisRepository()
    company_id = "company-999"

    first = repo.create({
        "company_id": company_id,
        "framework_version": "1.0",
        "analysis_date": "2026-09-04",
        "status": "Completed",
        "decision": "Buy",
        "confidence": 72,
        "overall_score": 7.6,
        "notes": "v1",
        "version_number": 1,
        "previous_analysis_id": None,
        "change_summary": "Initial draft",
    })

    second = repo.create_version(company_id, first["id"], {
        "analysis_date": "2026-09-20",
        "status": "Completed",
        "decision": "Strong Buy",
        "confidence": 80,
        "overall_score": 8.4,
        "notes": "v2",
        "change_summary": "Improved thesis",
    })

    versions = repo.get_versions_for_company(company_id)
    assert len(versions) == 2
    assert versions[0]["version_number"] == 1
    assert versions[1]["version_number"] == 2
    assert repo.get_by_id(first["id"])["notes"] == "v1"
    assert repo.get_by_id(first["id"])["decision"] == "Buy"
    assert second["previous_analysis_id"] == first["id"]
