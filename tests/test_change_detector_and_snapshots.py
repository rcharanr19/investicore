from __future__ import annotations

import pytest

from repositories.financial_metric_repository import FinancialMetricRepository
from repositories.financial_period_repository import FinancialPeriodRepository
from repositories.research_alert_repository import ResearchAlertRepository
from repositories.valuation_snapshot_repository import ValuationSnapshotRepository
from services.change_detector import SECChangeDetector


def test_change_detector_alerts():
    period_repo = FinancialPeriodRepository()
    metric_repo = FinancialMetricRepository()
    alert_repo = ResearchAlertRepository()

    # Create 2 annual periods for comp-alert-1
    p_curr = period_repo.create({
        "company_id": "comp-alert-1",
        "fiscal_year": 2025,
        "period_type": "Annual",
        "period_end": "2025-12-31",
    })
    p_prev = period_repo.create({
        "company_id": "comp-alert-1",
        "fiscal_year": 2024,
        "period_type": "Annual",
        "period_end": "2024-12-31",
    })

    # Add metrics: Cash declined from 100M to 60M (-40%), Shares increased from 10M to 12M (+20%)
    metric_repo.create({"company_id": "comp-alert-1", "financial_period_id": p_prev["id"], "metric_name": "cash", "metric_value": 100000000.0})
    metric_repo.create({"company_id": "comp-alert-1", "financial_period_id": p_curr["id"], "metric_name": "cash", "metric_value": 60000000.0})

    metric_repo.create({"company_id": "comp-alert-1", "financial_period_id": p_prev["id"], "metric_name": "shares_diluted", "metric_value": 10000000.0})
    metric_repo.create({"company_id": "comp-alert-1", "financial_period_id": p_curr["id"], "metric_name": "shares_diluted", "metric_value": 12000000.0})

    detector = SECChangeDetector(period_repo=period_repo, metric_repo=metric_repo, alert_repo=alert_repo)
    alerts = detector.run_change_detection("comp-alert-1")

    assert len(alerts) == 2
    types = {a["alert_type"] for a in alerts}
    assert "CASH_DECLINE" in types
    assert "SHARE_DILUTION" in types


def test_valuation_snapshot_repository_crud():
    snap_repo = ValuationSnapshotRepository()
    snap = snap_repo.create({
        "company_id": "comp-snap-1",
        "snapshot_date": "2026-09-08",
        "share_price": 8.50,
        "shares": 10.0,
        "expected_value": 12.00,
        "expected_return": 41.2,
        "thesis_status": "INVEST",
    })

    assert snap["id"] is not None
    assert snap["share_price"] == 8.50

    snaps = snap_repo.list_by_company("comp-snap-1")
    assert len(snaps) == 1
    assert snaps[0]["id"] == snap["id"]

    assert snap_repo.delete(snap["id"]) is True
    assert len(snap_repo.list_by_company("comp-snap-1")) == 0
