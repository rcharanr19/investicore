from __future__ import annotations

import pytest

from repositories.catalyst_repository import CatalystRepository
from repositories.sec_filing_repository import SECFilingRepository
from services.sec.catalysts import SECCatalystDetector


def test_classify_8k_items():
    detector = SECCatalystDetector()
    items_raw = "Item 1.01; Item 2.01, Item 5.02"
    parsed = detector.classify_8k_items(items_raw)

    assert len(parsed) == 3
    types = [p["catalyst_type"] for p in parsed]
    assert "Contract / Strategic Agreement" in types
    assert "Asset Sale / Acquisition" in types
    assert "Management Change" in types


def test_extract_catalysts_from_filings():
    filing_repo = SECFilingRepository()
    cat_repo = CatalystRepository()

    # Create dummy 8-K
    filing_repo.create({
        "company_id": "comp-cat-1",
        "accession_number": "0001-8k-001",
        "form_type": "8-K",
        "filing_date": "2026-08-15",
        "items": "2.01, 8.01",
    })

    detector = SECCatalystDetector()
    extracted = detector.extract_catalysts_from_filings(
        company_id="comp-cat-1",
        filing_repo=filing_repo,
        catalyst_repo=cat_repo,
    )

    assert len(extracted) == 2
    cats = cat_repo.list_by_company("comp-cat-1")
    assert len(cats) == 2
    assert cats[0]["status"] == "Announced"


def test_calculate_catalyst_score():
    detector = SECCatalystDetector()
    res = detector.calculate_catalyst_score(
        probability_pct=80.0,
        value_impact_per_share=5.00,
        time_to_realization_years=2.0,
    )
    # Expected Impact = 0.80 * 5.00 = 4.00
    # Velocity Score = 4.00 / 2.0 = 2.00
    assert res["expected_value_impact"] == 4.00
    assert res["catalyst_velocity_score"] == 2.00
