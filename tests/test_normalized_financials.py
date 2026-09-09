from __future__ import annotations

from repositories.financial_metric_repository import FinancialMetricRepository
from repositories.financial_period_repository import FinancialPeriodRepository
from services.normalized_financials import (
    calculate_normalized_cagr,
    calculate_normalized_ttm,
    get_normalized_financial_records,
)


def _add_metric(metric_repo: FinancialMetricRepository, company_id: str, period_id: str, name: str, value: float) -> None:
    metric_repo.create(
        {
            "company_id": company_id,
            "financial_period_id": period_id,
            "metric_name": name,
            "metric_value": value,
            "source_concept": name,
            "confidence": "HIGH",
        }
    )


def test_normalized_financial_records_use_sec_metrics_in_millions():
    period_repo = FinancialPeriodRepository()
    metric_repo = FinancialMetricRepository()
    company_id = "comp-normalized-1"

    period = period_repo.create(
        {
            "company_id": company_id,
            "fiscal_year": 2025,
            "period_type": "Annual",
            "fiscal_period": "FY",
            "period_end": "2025-12-31",
        }
    )
    _add_metric(metric_repo, company_id, period["id"], "revenue", 2_500_000_000.0)
    _add_metric(metric_repo, company_id, period["id"], "free_cash_flow", 250_000_000.0)
    _add_metric(metric_repo, company_id, period["id"], "total_debt", 80_000_000.0)
    _add_metric(metric_repo, company_id, period["id"], "shares_diluted", 50_000_000.0)
    _add_metric(metric_repo, company_id, period["id"], "eps_diluted", 3.25)

    records = get_normalized_financial_records(company_id, period_repo, metric_repo, period_type="Annual")

    assert len(records) == 1
    assert records[0]["period_label"] == "FY2025"
    assert records[0]["revenue"] == 2500.0
    assert records[0]["free_cash_flow"] == 250.0
    assert records[0]["debt"] == 80.0
    assert records[0]["shares_outstanding"] == 50.0
    assert records[0]["eps"] == 3.25


def test_normalized_ttm_sums_flows_and_uses_latest_balance_sheet_values():
    period_repo = FinancialPeriodRepository()
    metric_repo = FinancialMetricRepository()
    company_id = "comp-normalized-ttm"

    for quarter in range(1, 5):
        period = period_repo.create(
            {
                "company_id": company_id,
                "fiscal_year": 2025,
                "period_type": "Quarterly",
                "fiscal_period": f"Q{quarter}",
                "period_end": f"2025-{quarter * 3:02d}-30",
            }
        )
        _add_metric(metric_repo, company_id, period["id"], "revenue", quarter * 100_000_000.0)
        _add_metric(metric_repo, company_id, period["id"], "free_cash_flow", quarter * 10_000_000.0)
        _add_metric(metric_repo, company_id, period["id"], "cash", quarter * 5_000_000.0)

    ttm = calculate_normalized_ttm(company_id, period_repo, metric_repo)

    assert ttm is not None
    assert ttm["revenue"] == 1000.0
    assert ttm["free_cash_flow"] == 100.0
    assert ttm["cash"] == 20.0


def test_normalized_cagr_uses_normalized_records():
    period_repo = FinancialPeriodRepository()
    metric_repo = FinancialMetricRepository()
    company_id = "comp-normalized-cagr"

    for year, revenue in [(2023, 100_000_000.0), (2024, 110_000_000.0), (2025, 121_000_000.0)]:
        period = period_repo.create(
            {
                "company_id": company_id,
                "fiscal_year": year,
                "period_type": "Annual",
                "fiscal_period": "FY",
                "period_end": f"{year}-12-31",
            }
        )
        _add_metric(metric_repo, company_id, period["id"], "revenue", revenue)

    cagr = calculate_normalized_cagr(company_id, "revenue", period_repo, metric_repo)

    assert cagr is not None
    assert round(cagr, 2) == 10.00