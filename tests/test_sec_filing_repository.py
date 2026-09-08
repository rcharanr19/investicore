from __future__ import annotations

import pytest

from repositories.sec_filing_repository import SECFilingRepository


def test_sec_filing_repository_crud():
    repo = SECFilingRepository()

    # Create filing
    rec = repo.create(
        {
            "company_id": "comp-123",
            "accession_number": "0000320193-24-000100",
            "form_type": "10-K",
            "filing_date": "2024-11-01",
            "report_date": "2024-09-30",
            "primary_document": "aapl-20240930.htm",
            "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000100/aapl-20240930.htm",
            "is_xbrl": True,
        }
    )

    assert rec["id"] is not None
    assert rec["accession_number"] == "0000320193-24-000100"
    assert rec["parsed_status"] == "Unparsed"

    # Lookup by accession
    found = repo.get_by_accession("comp-123", "0000320193-24-000100")
    assert found is not None
    assert found["id"] == rec["id"]

    # List by company with form filter
    k_list = repo.list_by_company("comp-123", form_types=["10-K"])
    assert len(k_list) == 1
    q_list = repo.list_by_company("comp-123", form_types=["10-Q"])
    assert len(q_list) == 0

    # Update
    updated = repo.update(rec["id"], {"parsed_status": "Parsed"})
    assert updated is not None
    assert updated["parsed_status"] == "Parsed"

    # Delete
    assert repo.delete(rec["id"]) is True
    assert repo.get_by_id(rec["id"]) is None
