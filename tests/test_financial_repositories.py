from __future__ import annotations

import pytest

from repositories.financial_metric_repository import FinancialMetricRepository
from repositories.financial_period_repository import FinancialPeriodRepository


def test_financial_period_repository_crud():
    repo = FinancialPeriodRepository()

    # Create period
    p = repo.create({
        "company_id": "comp-test-1",
        "fiscal_year": 2024,
        "period_type": "Annual",
        "fiscal_period": "FY",
        "period_end": "2024-12-31",
        "period_start": "2024-01-01",
    })

    assert p["id"] is not None
    assert p["fiscal_year"] == 2024
    assert p["period_type"] == "Annual"

    # Lookup / get_or_create existing
    existing = repo.get_or_create(
        company_id="comp-test-1",
        fiscal_year=2024,
        period_type="Annual",
        period_end="2024-12-31",
        fiscal_period="FY",
    )
    assert existing["id"] == p["id"]

    # List by company
    p_list = repo.list_by_company("comp-test-1", period_type="Annual")
    assert len(p_list) == 1
    assert p_list[0]["id"] == p["id"]


def test_financial_metric_repository_crud():
    repo = FinancialMetricRepository()

    # Create metric
    m = repo.create({
        "company_id": "comp-test-1",
        "financial_period_id": "period-1",
        "metric_name": "revenue",
        "metric_value": 150000000.0,
        "source_concept": "Revenues",
        "confidence": "HIGH",
    })

    assert m["id"] is not None
    assert m["metric_value"] == 150000000.0
    assert m["confidence"] == "HIGH"

    # List by period
    by_p = repo.list_by_period("period-1")
    assert len(by_p) == 1
    assert by_p[0]["metric_name"] == "revenue"

    # Delete by period
    assert repo.delete_by_period("period-1") is True
    assert len(repo.list_by_period("period-1")) == 0
